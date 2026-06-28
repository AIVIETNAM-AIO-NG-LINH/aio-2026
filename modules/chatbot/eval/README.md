# Đánh giá RAG chatbot

Tài nguyên cho command `python manage.py eval_rag` (xem
`modules/chatbot/app/management/commands/eval_rag.py`).

```
eval/
├── datasets/   # bộ golden QA đầu vào (--dataset)
│   ├── golden_qa.json              # bộ chính (28 câu)
│   ├── golden_qa.example.json      # mẫu/template để tham khảo định dạng
│   └── golden_qa_relational.json   # bộ câu hỏi quan hệ (đánh giá KG)
└── results/    # kết quả đầu ra đã chạy (--out)
    ├── full_out.json        # full (bm25 + hybrid + hybrid_rerank), 28 câu
    ├── retrieval_out.json   # chỉ tầng truy hồi, 28 câu
    ├── retrieval_fixed.json # truy hồi (bản đã sửa), 28 câu
    ├── kg_on.json           # A/B: --lightrag on (8 câu)
    ├── kg_off.json          # A/B: --lightrag off (8 câu)
    └── kg_out.json          # KG hybrid_rerank, 28 câu
```

## Chạy nhanh

```bash
# Chỉ tầng truy hồi (không tốn token)
python manage.py eval_rag \
  --dataset modules/chatbot/eval/datasets/golden_qa.json \
  --out modules/chatbot/eval/results/retrieval_out.json

# Đầy đủ (sinh + LLM-as-judge) — tốn token Gemini
python manage.py eval_rag \
  --dataset modules/chatbot/eval/datasets/golden_qa.json \
  --generation --judge \
  --out modules/chatbot/eval/results/full_out.json

# A/B bật/tắt Knowledge Graph
python manage.py eval_rag --dataset modules/chatbot/eval/datasets/golden_qa.json --lightrag on  --out modules/chatbot/eval/results/kg_on.json
python manage.py eval_rag --dataset modules/chatbot/eval/datasets/golden_qa.json --lightrag off --out modules/chatbot/eval/results/kg_off.json
```

`datasets/` là đầu vào (giữ lại); `results/` là tạo sinh, có thể tạo lại bằng cách chạy lại command.
