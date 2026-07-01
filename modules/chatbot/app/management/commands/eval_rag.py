"""Đánh giá pipeline RAG của chatbot — 3 tầng (truy hồi / sinh / hệ thống).

Chạy:  python manage.py eval_rag --dataset modules/chatbot/eval/datasets/golden_qa.example.json
       (kết quả --out nên ghi vào modules/chatbot/eval/results/)

Bộ golden QA (JSON list), mỗi câu:
    {
      "question": "Cross-entropy loss định nghĩa thế nào?",
      "golden": [{"document_id": 12, "page": 7}],   # đoạn ĐÚNG để chấm truy hồi
      "reference_answer": "..."                       # (tùy chọn) đáp án mẫu
    }

Tầng truy hồi (luôn chạy, chỉ cần OpenSearch + embedding):
  - so (document_id[, page]) của top-K trả về với golden -> Recall@K, Precision@K, MRR, Hit@K
  - cấu hình: bm25 (BM25 thuần) / hybrid (BM25+kNN+RRF) / hybrid_rerank (live: +rerank +ngưỡng)

Tầng sinh (--generation): chạy agent ADK thật (đường trực tiếp, KHÔNG ghi DB chatbot),
  đo TTFT + latency (p50/p95). Thêm --judge: chấm Faithfulness + Answer-Relevance bằng
  Gemini (LLM-as-judge). --lightrag on|off để A/B bật/tắt KG mà không sửa .env.

LƯU Ý: command gọi dịch vụ THẬT (OpenSearch, Gemini, [LightRAG]) — cần env như khi chạy
hệ (GEMINI_API_KEY, OPENSEARCH_*). Tầng sinh tốn token Gemili nên là opt-in.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

# Các cấu hình truy hồi hợp lệ cho --configs.
_RETRIEVAL_CONFIGS = ("bm25", "hybrid", "hybrid_rerank")


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def _percentile(values: list[float], p: float) -> float:
    """Phân vị tuyến tính (p trong [0,1]); NaN nếu rỗng."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    return float(s[lo] * (hi - k) + s[hi] * (k - lo))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _matches(chunk: dict[str, Any], gold: dict[str, Any]) -> bool:
    """Một chunk trả về có khớp 1 đoạn golden không (document_id [+ page nếu có])."""
    if str(chunk.get("document_id")) != str(gold.get("document_id")):
        return False
    gold_page = gold.get("page")
    if gold_page is None:  # golden không chỉ định trang -> khớp ở mức tài liệu
        return True
    return chunk.get("page") == gold_page


def _dcg(rels: list[float]) -> float:
    """Discounted Cumulative Gain: sum rel_i / log2(rank_i + 1) (rank 1-based)."""
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def _novel_rels(topk: list[dict[str, Any]], golden: list[dict[str, Any]]) -> list[float]:
    """Relevance nhị phân, credit MỖI golden đúng MỘT lần (tại lần khớp đầu tiên).

    Một trang golden có thể có nhiều child-chunk; nếu đếm trùng thì nDCG/MAP vượt 1.
    Coi vị trí là 'có ích & mới' chỉ khi nó khớp một golden CHƯA được tính.
    """
    seen: set[int] = set()
    rels: list[float] = []
    for c in topk:
        novel = False
        for gi, g in enumerate(golden):
            if gi not in seen and _matches(c, g):
                seen.add(gi)
                novel = True
                break
        rels.append(1.0 if novel else 0.0)
    return rels


def _ndcg(topk: list[dict[str, Any]], golden: list[dict[str, Any]], top_k: int) -> float:
    """nDCG@K nhị phân: DCG của thứ hạng thực / DCG của thứ hạng lý tưởng (≤ 1)."""
    rels = _novel_rels(topk, golden)
    ideal = _dcg([1.0] * min(len(golden), top_k))
    return (_dcg(rels) / ideal) if ideal > 0 else 0.0


def _average_precision(topk: list[dict[str, Any]], golden: list[dict[str, Any]], top_k: int) -> float:
    """AP@K: trung bình Precision@i tại mỗi golden đúng MỚI (cơ sở của MAP; ≤ 1)."""
    rels = _novel_rels(topk, golden)
    hits = 0
    score = 0.0
    for i, r in enumerate(rels, start=1):
        if r > 0:
            hits += 1
            score += hits / i
    denom = min(len(golden), top_k)
    return (score / denom) if denom else 0.0


def _tokens(s: str) -> list[str]:
    return (s or "").lower().split()


def _lcs_len(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[len(b)]


def _rouge_l(pred: str, ref: str) -> float:
    """ROUGE-L F1 dựa trên dãy con chung dài nhất (LCS) giữa pred và ref."""
    p, r = _tokens(pred), _tokens(ref)
    if not p or not r:
        return 0.0
    lcs = _lcs_len(p, r)
    if lcs == 0:
        return 0.0
    prec, rec = lcs / len(p), lcs / len(r)
    return 2 * prec * rec / (prec + rec)


def _bleu(pred: str, ref: str, max_n: int = 4) -> float:
    """BLEU-4 (đối xứng 1 tham chiếu) + brevity penalty + smoothing nhẹ."""
    from collections import Counter

    p, r = _tokens(pred), _tokens(ref)
    if not p or not r:
        return 0.0
    precisions: list[float] = []
    for n in range(1, max_n + 1):
        pg = [tuple(p[i : i + n]) for i in range(len(p) - n + 1)]
        rg = [tuple(r[i : i + n]) for i in range(len(r) - n + 1)]
        if not pg:
            precisions.append(1e-9)
            continue
        rc = Counter(rg)
        overlap = sum(min(c, rc[g]) for g, c in Counter(pg).items())
        precisions.append((overlap / len(pg)) or 1e-9)
    geo = math.exp(sum(math.log(x) for x in precisions) / max_n)
    bp = 1.0 if len(p) > len(r) else math.exp(1 - len(r) / len(p))
    return bp * geo


def _retrieval_metrics(
    retrieved: list[dict[str, Any]], golden: list[dict[str, Any]], top_k: int
) -> dict[str, float]:
    """Recall@K, Precision@K, MRR, Hit@K, nDCG@K, MAP@K cho MỘT câu hỏi."""
    topk = retrieved[:top_k]
    if not golden:
        nan = float("nan")
        return {"recall": nan, "precision": nan, "mrr": nan, "hit": nan, "ndcg": nan, "map": nan}

    # rank (1-based) của chunk liên quan đầu tiên
    first_rel_rank = 0
    for i, c in enumerate(topk, start=1):
        if any(_matches(c, g) for g in golden):
            first_rel_rank = i
            break

    # Tính relevance theo từng golden DUY NHẤT (1 trang golden có nhiều child-chunk;
    # nếu đếm trùng thì precision/nDCG/MAP vượt trần). Cả bộ dùng chung cách đếm này.
    rels = _novel_rels(topk, golden)
    matched_golden = sum(rels)  # số golden phân biệt tìm thấy trong top-K

    ideal = _dcg([1.0] * min(len(golden), top_k))
    ap_hits = 0
    ap_score = 0.0
    for i, r in enumerate(rels, start=1):
        if r > 0:
            ap_hits += 1
            ap_score += ap_hits / i
    denom = min(len(golden), top_k)

    return {
        "recall": matched_golden / len(golden),
        "precision": matched_golden / top_k,
        "mrr": (1.0 / first_rel_rank) if first_rel_rank else 0.0,
        "hit": 1.0 if first_rel_rank else 0.0,
        "ndcg": (_dcg(rels) / ideal) if ideal > 0 else 0.0,
        "map": (ap_score / denom) if denom else 0.0,
    }


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------
class Command(BaseCommand):
    help = "Đánh giá RAG (truy hồi/sinh/hệ thống) trên bộ golden QA và in bảng cho mục X."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dataset", required=True, help="Đường dẫn JSON bộ golden QA.")
        parser.add_argument("--top-k", type=int, default=5, help="Số đoạn cuối (mặc định 5).")
        parser.add_argument("--top-n", type=int, default=30, help="Số ứng viên hybrid (mặc định 30).")
        parser.add_argument("--rrf-k", type=int, default=60, help="Hằng số RRF (mặc định 60).")
        parser.add_argument(
            "--configs",
            default=",".join(_RETRIEVAL_CONFIGS),
            help=f"Cấu hình truy hồi, phẩy ngăn cách. Hợp lệ: {','.join(_RETRIEVAL_CONFIGS)}",
        )
        parser.add_argument("--limit", type=int, default=0, help="Giới hạn số câu (0 = tất cả).")
        parser.add_argument(
            "--generation",
            action="store_true",
            help="Chạy tầng sinh (agent ADK thật) + đo TTFT/latency. Tốn token Gemini.",
        )
        parser.add_argument(
            "--judge",
            action="store_true",
            help="Chấm Faithfulness/Answer-Relevance bằng LLM-as-judge (bật --generation).",
        )
        parser.add_argument("--judge-model", default="gemini-2.5-flash", help="Model làm judge.")
        parser.add_argument(
            "--lightrag",
            choices=("auto", "on", "off"),
            default="auto",
            help="Ghi đè LIGHTRAG_ENABLED cho lần chạy (auto = theo .env).",
        )
        parser.add_argument("--out", default="", help="Ghi kết quả chi tiết ra file JSON.")

    # -- main ---------------------------------------------------------------
    def handle(self, *args, **opts) -> None:
        import os

        # Ghi đè cờ KG nếu yêu cầu (đọc lúc chạy bởi LightRagQuerier()/index).
        if opts["lightrag"] != "auto":
            os.environ["LIGHTRAG_ENABLED"] = "true" if opts["lightrag"] == "on" else "false"
            self.stdout.write(f"[cfg] LIGHTRAG_ENABLED={os.environ['LIGHTRAG_ENABLED']}")

        dataset = self._load_dataset(opts["dataset"], opts["limit"])
        configs = self._parse_configs(opts["configs"])
        top_k, top_n, rrf_k = opts["top_k"], opts["top_n"], opts["rrf_k"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n== EVAL RAG | {len(dataset)} câu | top_k={top_k} top_n={top_n} rrf_k={rrf_k} =="
            )
        )

        results: dict[str, Any] = {
            "meta": {"n": len(dataset), "top_k": top_k, "top_n": top_n, "rrf_k": rrf_k},
            "retrieval": {},
        }

        # --- Tầng 1: truy hồi ---------------------------------------------
        retrieval_agg = self._run_retrieval(dataset, configs, top_k, top_n, rrf_k, results)

        # --- Tầng 2+3: sinh + hệ thống ------------------------------------
        gen_agg = None
        if opts["generation"]:
            gen_agg = self._run_generation(dataset, opts["judge"], opts["judge_model"], results)

        # --- In bảng tóm tắt cho mục X ------------------------------------
        self._print_report_table(retrieval_agg, gen_agg, top_k)

        if opts["out"]:
            Path(opts["out"]).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"\nĐã ghi chi tiết -> {opts['out']}"))

        self.stdout.write(self.style.SUCCESS("\neval_rag xong."))

    # -- dataset ------------------------------------------------------------
    def _load_dataset(self, path: str, limit: int) -> list[dict[str, Any]]:
        p = Path(path)
        if not p.exists():
            raise CommandError(f"Không thấy dataset: {path}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Dataset không phải JSON hợp lệ: {exc}") from exc
        if not isinstance(data, list) or not data:
            raise CommandError("Dataset phải là JSON list không rỗng.")
        for i, item in enumerate(data):
            if "question" not in item:
                raise CommandError(f"Câu #{i} thiếu 'question'.")
            item.setdefault("golden", [])
        return data[:limit] if limit > 0 else data

    def _parse_configs(self, raw: str) -> list[str]:
        configs = [c.strip() for c in raw.split(",") if c.strip()]
        bad = [c for c in configs if c not in _RETRIEVAL_CONFIGS]
        if bad:
            raise CommandError(f"Cấu hình không hợp lệ: {bad}. Hợp lệ: {_RETRIEVAL_CONFIGS}")
        return configs

    # -- Tầng 1: truy hồi ---------------------------------------------------
    def _run_retrieval(self, dataset, configs, top_k, top_n, rrf_k, results) -> dict[str, dict[str, float]]:
        # Lazy import (tránh side-effect lúc Django nạp mọi command).
        from modules.chatbot.app.opensearch.retriever import Retriever
        from modules.chatbot.app.rag.embedder import embed_query
        from modules.chatbot.app.tools.knowledge_base import search

        retriever = Retriever()
        agg: dict[str, dict[str, float]] = {}

        for cfg in configs:
            self.stdout.write(self.style.HTTP_INFO(f"\n[truy hồi] cấu hình: {cfg}"))
            per_q: list[dict[str, float]] = []
            n_empty = 0

            for idx, item in enumerate(dataset):
                q = item["question"]
                golden = item["golden"]
                try:
                    if cfg == "bm25":
                        retrieved = retriever.retrieve(q, None, top_n=top_n, rrf_k=rrf_k)
                    elif cfg == "hybrid":
                        qv = embed_query(q, retriever.vector_dims)
                        retrieved = retriever.retrieve(q, qv, top_n=top_n, rrf_k=rrf_k)
                    else:  # hybrid_rerank — đúng đường live (rerank + ngưỡng chống bịa)
                        retrieved = search(q, top_k=top_k, top_n=top_n)
                except Exception:  # noqa: BLE001 — 1 câu lỗi không làm hỏng cả lượt eval
                    logger.exception("[eval] lỗi truy hồi câu #%d (%s)", idx, cfg)
                    retrieved = []

                if not retrieved:
                    n_empty += 1
                per_q.append(_retrieval_metrics(retrieved, golden, top_k))

            n = len(per_q)
            agg[cfg] = {
                "recall": _mean([m["recall"] for m in per_q]),
                "precision": _mean([m["precision"] for m in per_q]),
                "mrr": _mean([m["mrr"] for m in per_q]),
                "hit": _mean([m["hit"] for m in per_q]),
                "ndcg": _mean([m["ndcg"] for m in per_q]),
                "map": _mean([m["map"] for m in per_q]),
                "empty": n_empty,
                "success_rate": (n - n_empty) / n if n else float("nan"),
            }
            results["retrieval"][cfg] = agg[cfg]
            a = agg[cfg]
            self.stdout.write(
                f"  Recall@{top_k}={a['recall']:.3f}  Precision@{top_k}={a['precision']:.3f}  "
                f"MRR={a['mrr']:.3f}  Hit@{top_k}={a['hit']:.3f}  nDCG@{top_k}={a['ndcg']:.3f}  "
                f"MAP@{top_k}={a['map']:.3f}  (trả rỗng: {n_empty}, success={a['success_rate']:.3f})"
            )
        return agg

    # -- Tầng 2+3: sinh + hệ thống -----------------------------------------
    def _run_generation(self, dataset, do_judge, judge_model, results) -> dict[str, Any]:
        self.stdout.write(self.style.HTTP_INFO("\n[sinh] chạy agent ADK thật (không ghi DB)…"))
        ttfts: list[float] = []
        lats: list[float] = []
        # judge (LLM-as-judge, kiểu RAGAS)
        faiths: list[float] = []
        rels: list[float] = []
        ctx_precs: list[float] = []
        ctx_recs: list[float] = []
        corrects: list[float] = []
        # so chuỗi với reference (lexical)
        rouges: list[float] = []
        bleus: list[float] = []
        per_q: list[dict[str, Any]] = []
        n_error = 0  # câu ném exception khi sinh
        n_empty = 0  # câu sinh ra câu trả lời rỗng
        wall = 0.0  # tổng thời gian sinh (đo throughput tuần tự, 1 client)

        for idx, item in enumerate(dataset):
            q = item["question"]
            ref = item.get("reference_answer") or ""
            try:
                out = self._answer_one(q)
            except Exception:  # noqa: BLE001
                logger.exception("[eval] lỗi sinh câu #%d", idx)
                n_error += 1
                continue

            if out["ttft"] is not None:
                ttfts.append(out["ttft"])
            lats.append(out["latency"])
            wall += out["latency"]
            if not out["answer"]:
                n_empty += 1

            row: dict[str, Any] = {
                "question": q,
                "answer": out["answer"],
                "n_contexts": len(out["contexts"]),
                "ttft": out["ttft"],
                "latency": out["latency"],
            }
            # ROUGE-L / BLEU vs reference (chỉ khi có reference) — lexical, đọc dè dặt
            if ref and out["answer"]:
                rl, bl = _rouge_l(out["answer"], ref), _bleu(out["answer"], ref)
                row["rouge_l"], row["bleu"] = rl, bl
                rouges.append(rl)
                bleus.append(bl)

            if do_judge:
                scores = self._judge(q, out["answer"], out["contexts"], ref, judge_model)
                if scores:
                    for key, bucket in (
                        ("faithfulness", faiths),
                        ("answer_relevance", rels),
                        ("context_precision", ctx_precs),
                        ("context_recall", ctx_recs),
                        ("correctness", corrects),
                    ):
                        if scores.get(key) is not None:
                            bucket.append(scores[key])
                    row["judge"] = scores
            per_q.append(row)
            self.stdout.write(
                f"  #{idx + 1}/{len(dataset)} ttft={out['ttft'] and round(out['ttft'], 2)}s "
                f"lat={out['latency']:.2f}s ctx={len(out['contexts'])}"
            )

        n_total = len(dataset)
        gen = {
            "ttft_p50": _percentile(ttfts, 0.5),
            "ttft_p95": _percentile(ttfts, 0.95),
            "latency_p50": _percentile(lats, 0.5),
            "latency_p95": _percentile(lats, 0.95),
            "faithfulness": _mean(faiths) if faiths else None,
            "answer_relevance": _mean(rels) if rels else None,
            "context_precision": _mean(ctx_precs) if ctx_precs else None,
            "context_recall": _mean(ctx_recs) if ctx_recs else None,
            "correctness": _mean(corrects) if corrects else None,
            "rouge_l": _mean(rouges) if rouges else None,
            "bleu": _mean(bleus) if bleus else None,
            "error_rate": n_error / n_total if n_total else float("nan"),
            "empty_rate": n_empty / n_total if n_total else float("nan"),
            "success_rate": (n_total - n_error - n_empty) / n_total if n_total else float("nan"),
            "throughput_seq_qps": (len(per_q) / wall) if wall > 0 else float("nan"),
            "n": len(per_q),
        }
        results["generation"] = {"agg": gen, "per_question": per_q}
        self.stdout.write(
            f"  TTFT p50={gen['ttft_p50']:.2f}s p95={gen['ttft_p95']:.2f}s | "
            f"latency p50={gen['latency_p50']:.2f}s p95={gen['latency_p95']:.2f}s | "
            f"throughput(tuần tự)={gen['throughput_seq_qps']:.3f} q/s"
        )
        self.stdout.write(
            f"  success={gen['success_rate']:.3f} error={gen['error_rate']:.3f} empty={gen['empty_rate']:.3f}"
        )
        if rouges:
            self.stdout.write(f"  ROUGE-L={gen['rouge_l']:.3f}  BLEU={gen['bleu']:.3f}  (lexical, dè dặt)")
        if do_judge:
            def _s(v):
                return "---" if v is None else round(v, 3)

            self.stdout.write(
                f"  Faithfulness={_s(gen['faithfulness'])}  Answer-Rel={_s(gen['answer_relevance'])}  "
                f"Context-Prec={_s(gen['context_precision'])}  Context-Rec={_s(gen['context_recall'])}  "
                f"Correctness={_s(gen['correctness'])}"
            )
        return gen

    def _answer_one(self, question: str) -> dict[str, Any]:
        """Chạy 1 lượt qua agent ADK (đường trực tiếp) -> {answer, contexts, ttft, latency}."""
        from asgiref.sync import async_to_sync
        from google.adk.agents.run_config import RunConfig, StreamingMode
        from google.genai import types

        from modules.chatbot.app.adk.constants import APP_NAME
        from modules.chatbot.app.adk.runner import get_runner, get_session_service
        from modules.chatbot.app.adk.session import create_session_with_history
        from modules.chatbot.app.adk.stream_handler import ADKStreamHandler

        prompt = self._build_prompt(question)
        ss = get_session_service()
        session = create_session_with_history(ss, "eval_oneoff", [])
        msg = types.Content(role="user", parts=[types.Part(text=prompt)])
        handler = ADKStreamHandler()

        answer_parts: list[str] = []
        contexts: list[dict[str, Any]] = []
        ttft: float | None = None
        t0 = time.perf_counter()
        try:
            for ev in get_runner().run(
                user_id="eval_oneoff",
                session_id=session.id,
                new_message=msg,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                for c in handler.process(ev):
                    if c.kind == "text" and c.text:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        answer_parts.append(c.text)
                    elif c.kind == "citations":
                        contexts = c.citations
        finally:
            latency = time.perf_counter() - t0
            try:  # dọn session in-memory (best-effort)
                async_to_sync(ss.delete_session)(
                    app_name=APP_NAME, user_id="eval_oneoff", session_id=session.id
                )
            except Exception:  # noqa: BLE001
                pass

        return {
            "answer": "".join(answer_parts).strip(),
            "contexts": contexts,
            "ttft": ttft,
            "latency": latency,
        }

    @staticmethod
    def _build_prompt(question: str) -> str:
        """Bọc câu hỏi giống luồng chat thật nếu có build_user_message; else dùng thô."""
        try:
            from modules.chatbot.app.chat_pipeline.prompt import build_user_message  # type: ignore

            built = build_user_message(question)
            # build_user_message có thể trả str hoặc cấu trúc Part — chỉ nhận str.
            if isinstance(built, str) and built.strip():
                return built
        except Exception:  # noqa: BLE001
            pass
        return question

    # các trường điểm LLM-judge trả về (đều [0,1])
    _JUDGE_FIELDS = ("faithfulness", "answer_relevance", "context_precision", "context_recall", "correctness")

    def _judge(self, question, answer, contexts, reference, model) -> dict[str, Any] | None:
        """LLM-as-judge kiểu RAGAS: chấm 5 chỉ số (0..1) bằng Gemini trong 1 lượt gọi.

        faithfulness, answer_relevance, context_precision, context_recall, correctness.
        context_recall/correctness cần REFERENCE; nếu không có reference thì để None.
        """
        from modules.base.app.clients.gemini_client import GeminiClient

        ctx = "\n\n".join((c.get("chunk_text") or "") for c in contexts).strip() or "(không có ngữ cảnh)"
        if not answer:
            return {k: 0.0 for k in self._JUDGE_FIELDS} | {"note": "empty answer"}

        ref_block = reference.strip() if reference else "(không có)"
        prompt = (
            "You are a strict RAG evaluator. Given a QUESTION, the retrieved CONTEXT, the model "
            "ANSWER and a REFERENCE answer, output ONLY a JSON object with these float fields in [0,1] "
            "(use null only if a field truly cannot be judged):\n"
            '  {"faithfulness": a, "answer_relevance": b, "context_precision": c, '
            '"context_recall": d, "correctness": e}\n'
            "- faithfulness = fraction of the ANSWER's claims supported by CONTEXT (1=grounded, 0=fabricated).\n"
            "- answer_relevance = how directly the ANSWER addresses the QUESTION.\n"
            "- context_precision = fraction of the CONTEXT that is relevant/useful for the QUESTION "
            "(high = little irrelevant noise).\n"
            "- context_recall = fraction of the REFERENCE answer's facts that ARE present in the CONTEXT "
            "(judges retrieval coverage; null if no REFERENCE).\n"
            "- correctness = how well the ANSWER matches the REFERENCE in meaning (null if no REFERENCE).\n"
            "No prose, no code fence — just the JSON.\n\n"
            f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}\n\nREFERENCE:\n{ref_block}\n\nANSWER:\n{answer}\n"
        )
        try:
            raw = GeminiClient().generate_text([prompt], model=model)
        except Exception:  # noqa: BLE001
            logger.exception("[eval] judge gọi Gemini lỗi")
            return None
        return self._parse_judge_json(raw)

    @staticmethod
    def _parse_judge_json(raw: str) -> dict[str, Any] | None:
        """Bóc JSON 5 điểm RAGAS-style từ output (chịu được code fence)."""
        import re

        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

        def _clip(v: Any) -> float | None:
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                return None

        return {k: _clip(obj.get(k)) for k in Command._JUDGE_FIELDS}

    # -- bảng cho mục X -----------------------------------------------------
    def _print_report_table(self, retrieval_agg, gen_agg, top_k) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n== BẢNG CHO MỤC X (điền vào báo cáo) =="))
        faith = "---"
        ttft = "---"
        if gen_agg:
            if gen_agg.get("faithfulness") is not None:
                faith = f"{gen_agg['faithfulness']:.3f}"
            if not math.isnan(gen_agg["ttft_p50"]):
                ttft = f"{gen_agg['ttft_p50']:.2f}"

        label = {
            "bm25": "Baseline (BM25 thuần)",
            "hybrid": "Hybrid (BM25 + kNN + RRF)",
            "hybrid_rerank": "Triển khai (hybrid + RRF + sàn cosine)",
        }
        header = (
            f"{'Cấu hình':<38} {'Recall@'+str(top_k):>9} {'MRR':>7} {'nDCG@'+str(top_k):>8} "
            f"{'Faithfulness':>13} {'TTFT(s)':>9}"
        )
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for cfg, a in retrieval_agg.items():
            # Faithfulness/TTFT đo ở tầng sinh dùng env hiện tại -> gắn vào dòng live (hybrid_rerank).
            fcol = faith if cfg == "hybrid_rerank" else "---"
            tcol = ttft if cfg == "hybrid_rerank" else "---"
            self.stdout.write(
                f"{label.get(cfg, cfg):<38} {a['recall']:>9.3f} {a['mrr']:>7.3f} {a['ndcg']:>8.3f} "
                f"{fcol:>13} {tcol:>9}"
            )

        # --- Khối "đo đầy đủ" cho cấu hình triển khai (live) ----------------
        live = retrieval_agg.get("hybrid_rerank") or next(iter(retrieval_agg.values()), {})
        self.stdout.write(self.style.MIGRATE_HEADING("\n== ĐO ĐẦY ĐỦ — cấu hình triển khai =="))

        def _fmt(v, nd=3):
            return "---" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{nd}f}"

        self.stdout.write("[Truy xuất]")
        for k, lbl in (("recall", f"Recall@{top_k}"), ("precision", f"Precision@{top_k}"),
                       ("mrr", "MRR"), ("hit", f"Hit@{top_k}"), ("ndcg", f"nDCG@{top_k}"),
                       ("map", f"MAP@{top_k}"), ("success_rate", "Success rate")):
            self.stdout.write(f"  {lbl:<16} {_fmt(live.get(k))}")

        if gen_agg:
            self.stdout.write("[Sinh — LLM-as-judge kiểu RAGAS]")
            for k, lbl in (("faithfulness", "Faithfulness"), ("answer_relevance", "Answer-Relevance"),
                           ("context_precision", "Context Precision"), ("context_recall", "Context Recall"),
                           ("correctness", "Correctness")):
                self.stdout.write(f"  {lbl:<18} {_fmt(gen_agg.get(k))}")
            self.stdout.write("[Sinh — so chuỗi với reference (lexical, dè dặt)]")
            self.stdout.write(f"  {'ROUGE-L':<18} {_fmt(gen_agg.get('rouge_l'))}")
            self.stdout.write(f"  {'BLEU':<18} {_fmt(gen_agg.get('bleu'))}")
            self.stdout.write("[Hệ thống]")
            self.stdout.write(f"  {'TTFT p50/p95':<18} {_fmt(gen_agg.get('ttft_p50'),2)} / {_fmt(gen_agg.get('ttft_p95'),2)} s")
            self.stdout.write(f"  {'Latency p50/p95':<18} {_fmt(gen_agg.get('latency_p50'),2)} / {_fmt(gen_agg.get('latency_p95'),2)} s")
            self.stdout.write(f"  {'Throughput (tuần tự)':<18} {_fmt(gen_agg.get('throughput_seq_qps'))} q/s")
            self.stdout.write(f"  {'Success/Error/Empty':<18} {_fmt(gen_agg.get('success_rate'))} / {_fmt(gen_agg.get('error_rate'))} / {_fmt(gen_agg.get('empty_rate'))}")

        self.stdout.write(
            "\nGhi chú: Context-P/R, Correctness là LLM-judge kiểu RAGAS (không dùng thư viện ragas). "
            "ROUGE-L/BLEU là lexical (tách từ theo khoảng trắng) — đọc dè dặt vì RAG mở. "
            "Throughput đo tuần tự 1 client (không phải load-test)."
        )
