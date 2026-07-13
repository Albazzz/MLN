# Quiz MLN – Ôn tập trắc nghiệm

Ứng dụng quiz tĩnh (HTML + CSS + JS), không cần server backend. Dữ liệu lấy từ `data.docx` (~540 câu, gồm biến thể kiểu hỏi khác).

## Tính năng

- **Ngẫu nhiên**: bật/tắt xáo trộn thứ tự câu; nút **Xáo lại**
- **Lưu câu sai**: trả lời sai → câu được lưu vào `localStorage`
- **Tab Câu sai**: làm lại chỉ các câu đã sai (cũng hỗ trợ ngẫu nhiên)
- Làm đúng ở tab Câu sai → tự gỡ khỏi danh sách sai
- **Mũi tên** Trước / Sau + phím `←` `→` + vuốt trên điện thoại
- Chọn đáp án bằng `1`–`4` hoặc `A`–`D`
- Nhảy tới số câu bất kỳ
- Reset điểm phiên / xóa toàn bộ câu sai

## Chạy local

Mở `index.html` bằng trình duyệt, hoặc:

```bash
# Python
python -m http.server 8080

# Node
npx serve .
```

Rồi vào `http://localhost:8080`.

## Deploy GitHub Pages

1. Tạo repo GitHub (public hoặc private + Pages enabled).
2. Đẩy các file:

   - `index.html`
   - `style.css`
   - `app.js`
   - `questions.js`

3. **Settings → Pages → Source**: Deploy from branch `main` / folder `/ (root)`.
4. Vài phút sau mở URL dạng `https://<user>.github.io/<repo>/`.

### Gợi ý `.gitignore` (tuỳ chọn)

```
data.docx
data_extracted.txt
parse_quiz.py
parse_log.txt
questions.json
.grok-changes/
css/
```

## Cập nhật ngân hàng câu hỏi

1. Cập nhật nội dung trong file nguồn (text/docx đã extract).
2. Chạy:

```bash
python parse_quiz.py
```

3. Commit lại `questions.js` (và `questions.json` nếu cần).

## Cấu trúc

| File | Vai trò |
|------|---------|
| `index.html` | Giao diện |
| `style.css` | Giao diện tối, responsive |
| `app.js` | Logic quiz, tab, localStorage |
| `questions.js` | Ngân hàng câu hỏi (`window.QUIZ_QUESTIONS`) |
| `parse_quiz.py` | Parse dữ liệu thô → JSON/JS |
