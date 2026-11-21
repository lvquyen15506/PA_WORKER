# Bắt đầu dự án PA Worker với Claude Code

Làm một lần, theo thứ tự. Mất khoảng 30–45 phút.

## Bước 1. Cài phần mềm cần thiết

| Phần mềm | Windows | macOS |
| --- | --- | --- |
| Git | https://git-scm.com/downloads/win (Claude Code cũng cần cái này trên Windows) | Có sẵn, hoặc `xcode-select --install` |
| Docker Desktop | https://www.docker.com/products/docker-desktop — bật WSL 2 khi được hỏi | Tải đúng bản Intel hoặc Apple Silicon |
| Python 3.12 | https://www.python.org/downloads/ — tích "Add python.exe to PATH" | `brew install python@3.12` |
| VS Code (khuyên dùng để xem code) | https://code.visualstudio.com | như Windows |

Python trên máy chỉ để skill `webapp-testing` chạy trình duyệt kiểm thử; ứng dụng thì chạy trong Docker.

## Bước 2. Cài Claude Code

Windows (mở **PowerShell**):
```powershell
irm https://claude.ai/install.ps1 | iex
```

macOS (mở **Terminal**):
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Mở cửa sổ terminal mới, gõ `claude --version` để kiểm tra.

## Bước 3. Tạo thư mục dự án từ bộ khởi đầu

1. Giải nén `pa-worker-starter.zip` ra nơi bạn muốn, ví dụ `D:\Projects\pa-worker` hoặc `~/Projects/pa-worker`.
2. Mở terminal **trong thư mục đó** rồi chạy:

```bash
git init
git add .
git commit -m "Khởi tạo bộ khởi đầu PA Worker"
```

Trong thư mục đã có:
```
CLAUDE.md                     quy tắc dự án, Claude đọc mỗi phiên
.claude/skills/pa-ui/         hệ thống giao diện PA Worker
docs/yeu-cau.md               tài liệu yêu cầu khách đã duyệt
docs/quy-trinh-tiep-nhan.png  sơ đồ quy trình
docs/phases.md                kế hoạch 9 phase + câu lệnh mẫu
docs/tien-do.md               nhật ký tiến độ
.gitignore
```

## Bước 4. Thêm skill kiểm thử giao diện `webapp-testing`

Windows (PowerShell, trong thư mục dự án):
```powershell
git clone --depth 1 https://github.com/anthropics/skills $env:TEMP\anthropic-skills
Copy-Item -Recurse $env:TEMP\anthropic-skills\skills\webapp-testing .claude\skills\webapp-testing
pip install playwright
python -m playwright install chromium
```

macOS (Terminal, trong thư mục dự án):
```bash
git clone --depth 1 https://github.com/anthropics/skills /tmp/anthropic-skills
cp -r /tmp/anthropic-skills/skills/webapp-testing .claude/skills/webapp-testing
pip3 install playwright
python3 -m playwright install chromium
```

Không cài skill `frontend-design` cho dự án này: skill đó cố làm giao diện "khác biệt", trái với quy tắc `pa-ui`.

## Bước 5. Mở Claude Code và cài plugin

Trong thư mục dự án:
```bash
claude
```
Lần đầu sẽ mở trình duyệt để đăng nhập tài khoản Claude.

Trong Claude Code, gõ lần lượt (mỗi lệnh chọn phạm vi **Project** khi được hỏi):
```
/plugin install feature-dev@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install commit-commands@claude-plugins-official
```
Nếu báo không tìm thấy marketplace: `/plugin marketplace add anthropics/claude-plugins-official` rồi cài lại.

Gõ `/` để kiểm tra: phải thấy `pa-ui`, `webapp-testing` và các lệnh của plugin vừa cài.

## Bước 6. Bắt đầu Phase 0

Mở `docs/phases.md`, chép câu lệnh mẫu của **Phase 0** dán vào Claude Code. Trả lời các câu hỏi Claude nêu ra, rồi bảo Claude ghi quyết định vào `docs/tien-do.md`.

Từ đó, mỗi phase:
1. `/clear` để bắt đầu phiên sạch.
2. **Shift+Tab** đến khi thấy *plan mode*.
3. Dán câu lệnh mẫu của phase, đọc kế hoạch Claude đưa ra, góp ý hoặc duyệt.
4. Để Claude code; khi Claude hỏi quyền chạy lệnh, đọc rồi mới bấm Yes.
5. Cuối phase: test đạt → xem ảnh chụp màn hình → `/code-review` → cập nhật `docs/tien-do.md` → commit.

## Mẹo

- Muốn tiếp tục phiên hôm trước: `claude -c`.
- Thấy giao diện lệch chuẩn: "Kiểm tra trang này theo mục 10 của skill pa-ui và sửa cho khớp /ui-kit."
- Claude làm lan sang phase khác: "Dừng. Chỉ làm đúng phạm vi Phase N trong docs/phases.md."
- Đừng để một phiên quá dài; hết một phase thì `/clear`.
