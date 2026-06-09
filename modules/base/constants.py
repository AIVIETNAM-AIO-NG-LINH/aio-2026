"""Hằng số dùng chung — clone `app/Helpers/Global/constants.php` (phần liên quan).

Bên Laravel tên là `RES_FAILD` (typo gốc). Project mới dùng tên đúng chính tả
`RES_FAILED`; giá trị giữ nguyên để shape response không đổi với FE.
"""

# Cờ `success` trong body response.
RES_SUCCESS = 1
RES_FAILED = 0
