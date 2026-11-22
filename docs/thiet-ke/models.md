# Danh sách model Django – PA Worker

Phase 1 · Ngày 21/11/2026 · Cập nhật v1.1 ngày 23/11/2026 · Dựa trên `docs/thiet-ke/erd.md` và `docs/lam-ro-yeu-cau.md` câu 1–47 (câu 39–47 là phiếu thay đổi v1.1). Tên bảng, cột, quan hệ phải **khớp** với ERD; khi sửa một bên phải sửa bên kia.

## 1. Quy ước

- Cột `xxx_id` trong ERD là trường `ForeignKey`/`OneToOneField` tên `xxx` trong Django (ví dụ `created_by_id` ↔ `created_by`).
- Mọi `ForeignKey` dùng `on_delete=PROTECT` (không xóa cứng bản ghi có liên kết), trừ khi ghi khác.
- Cột **Bắt buộc**:
  - **Có**: NOT NULL ở CSDL và bắt buộc trên form.
  - **Nháp**: bắt buộc ngay từ lần lưu Nháp (câu 5).
  - **Gửi duyệt**: được để trống khi Nháp, bắt buộc khi chuyển Nháp/Cần bổ sung → Chờ duyệt (CSDL cho phép rỗng).
  - **Theo điều kiện**: ghi trong cột Ghi chú.
  - **Tự động**: hệ thống điền, người dùng không sửa.
  - **Không**: không bắt buộc.
- Trường mã hóa dùng `EncryptedTextField` (tự viết trong `apps/core/crypto.py`, Fernet, khóa `FIELD_ENCRYPTION_KEY`). Trường băm dùng `CharField(64)` chứa HMAC-SHA256 hex (khóa `HASH_KEY`). Thiếu hoặc sai một trong hai khóa thì ứng dụng không khởi động (câu 31).
- Giới tính chỉ có Nam, Nữ (câu 37).
- Tệp dùng `FileField` với storage riêng `PrivateStorage` (thư mục `/app/private_media`, nằm trong volume `media`, **không** có URL public). Tên tệp là chuỗi ngẫu nhiên `uuid4().hex` + đuôi theo định dạng thật.
- Ngày giờ lưu UTC, hiển thị Asia/Ho_Chi_Minh, định dạng dd/mm/yyyy.

### Ánh xạ bảng ERD → model

| App | Model | Bảng ERD | Bảng CSDL |
| --- | --- | --- | --- |
| accounts | `Role` | Roles | `accounts_role` |
| accounts | `User` | Users | `accounts_user` |
| accounts | `LoginHistory` | LoginHistory | `accounts_loginhistory` |
| audit | `AuditLog` | AuditLogs | `audit_auditlog` |
| audit | `AuditPersonalValue` | AuditPersonalValues | `audit_auditpersonalvalue` |
| core | `Department` | Departments | `core_department` |
| core | `Section` | Sections | `core_section` |
| core | `Team` | Teams | `core_team` |
| core | `Position` | Positions | `core_position` |
| core | `Shift` | Shifts | `core_shift` |
| core | `ApplicationSource` | ApplicationSources | `core_applicationsource` |
| core | `EducationLevel` | EducationLevels | `core_educationlevel` |
| core | `ClientCompany` | ClientCompanies | `core_clientcompany` |
| core | `RequiredDocumentGroup` | RequiredDocumentGroups | `core_requireddocumentgroup` |
| core | `DocumentType` | DocumentTypes | `core_documenttype` |
| core | `SystemSetting` | Settings | `core_systemsetting` |
| core | `CodeSequence` | CodeSequences | `core_codesequence` |
| core | `QrFormat` | QrFormats | `core_qrformat` |
| workers | `Worker` | Workers | `workers_worker` |
| workers | `IdentityDocument` | IdentityDocuments | `workers_identitydocument` |
| workers | `IdentityFieldSource` | IdentityFieldSources | `workers_identityfieldsource` |
| workers | `EmergencyContact` | EmergencyContacts | `workers_emergencycontact` |
| workers | `DataConsent` | DataConsents | `workers_dataconsent` |
| workers | `StatusChange` | StatusChanges | `workers_statuschange` |
| workers | `AnonymizationRecord` | AnonymizationRecords | `workers_anonymizationrecord` |
| workers | `AnonymizationItem` | AnonymizationItems | `workers_anonymizationitem` |
| documents | `WorkerDocument` | WorkerDocuments | `documents_workerdocument` |
| intake | `IntakeSession` | IntakeSessions | `intake_intakesession` |
| recruitment | `Application` | Applications | `recruitment_application` |
| recruitment | `Education` | Education | `recruitment_education` |
| recruitment | `Certificate` | Certificates | `recruitment_certificate` |
| recruitment | `WorkExperience` | WorkExperiences | `recruitment_workexperience` |
| employment | `Employment` | Employments | `employment_employment` |
| employment | `EmploymentHistory` | EmploymentHistory | `employment_employmenthistory` |
| employment | `Contract` | Contracts | `employment_contract` |
| employment | `WorkAssignment` | WorkAssignments | `employment_workassignment` |
| employment | `SalaryHistory` | SalaryHistory | `employment_salaryhistory` |
| reports | — | — | không có model |

37 model (34 của v1.0 + `ClientCompany`, `WorkAssignment`, `SalaryHistory` của v1.1). `workers` và `documents` trỏ lẫn nhau (`DataConsent.document` → `WorkerDocument`, `WorkerDocument.worker` → `Worker`); khai báo bằng chuỗi `"documents.WorkerDocument"` để tránh import vòng.

## 2. TextChoices

Khai báo **một chỗ** trong `apps/core/choices.py`. Không viết chuỗi trạng thái ở nơi khác. Template filter `status_badge` (Phase 3) lấy màu theo bảng pa-ui mục 5.

### Bốn bộ trạng thái (duy nhất được phép, CLAUDE.md)

| TextChoices | Mã → Nhãn | Dùng ở |
| --- | --- | --- |
| `RecruitmentStatus` | `NEW` Mới nộp · `SCREENING` Đang sàng lọc · `INTERVIEW` Hẹn phỏng vấn · `PASSED` Đạt · `FAILED` Không đạt · `DECLINED` Ứng viên từ chối | `Application.status` |
| `VerificationStatus` | `DRAFT` Nháp · `PENDING` Chờ duyệt · `NEEDS_INFO` Cần bổ sung · `VERIFIED` Đã xác minh · `REJECTED` Bị từ chối · `ARCHIVED` Lưu trữ | `Worker.verification_status`, `StatusChange.from_status/to_status` |
| `WorkStatus` | `AWAITING` Chờ nhận việc · `PROBATION` Thử việc · `ACTIVE` Đang làm việc · `SUSPENDED` Tạm hoãn · `RESIGNED` Đã nghỉ việc | `Employment.work_status`, `EmploymentHistory.from_work_status/to_work_status` |
| `DocumentVerificationStatus` | `UNVERIFIED` Chưa xác minh · `MATCHED` Đã đối chiếu bản gốc · `INVALID` Không hợp lệ | `WorkerDocument.verification_status` (chỉ tab Tài liệu) |

**v1.1 không thêm `TextChoices` nào**: `ClientCompany`, `WorkAssignment`, `SalaryHistory` không có trường trạng thái. "Đang diễn ra / đã kết thúc" của đợt làm việc suy ra từ `start_date`/`end_date` và hiển thị bằng chữ thường hoặc nhãn "Sắp hết hạn" sẵn có (pa-ui mục 5), không thêm nhãn, không lưu, không tạo bộ trạng thái thứ năm. `AuditAction` dùng `CREATE`, `UPDATE` có sẵn; `RetentionBasis` giữ nguyên 6 căn cứ (câu 44: mốc 10 năm vẫn là ngày nghỉ việc).

### Danh sách giá trị khác (không phải trạng thái)

| TextChoices | Mã → Nhãn |
| --- | --- |
| `RoleCode` | `ADMIN` Admin · `HR_MANAGER` Quản lý nhân sự · `HR_STAFF` Nhân viên HR · `VIEWER` Viewer |
| `Gender` | `MALE` Nam · `FEMALE` Nữ |
| `IdDocType` | `CCCD_2021` CCCD gắn chip (mẫu 2021) · `CAN_CUOC_2024` Thẻ Căn cước (từ 01/7/2024) · `CCCD_2016` CCCD mã vạch (mẫu 2016) |
| `ConsentMethod` | `PAPER` Ký giấy · `ELECTRONIC` Xác nhận điện tử |
| `FieldSource` | `QR` QR · `OCR` OCR · `MANUAL` Nhập tay |
| `ResignReason` | `SELF` Tự nghỉ · `CONTRACT_END` Hết hợp đồng · `TERMINATED` Chấm dứt hợp đồng · `OTHER` Khác |
| `ContractType` | `PROBATION` Thử việc · `FIXED_TERM` Xác định thời hạn · `INDEFINITE` Không xác định thời hạn |
| `EmploymentChangeType` | `ONBOARD` Tiếp nhận vào làm · `TRANSFER` Điều chuyển · `POSITION_CHANGE` Đổi chức danh · `SHIFT_CHANGE` Đổi ca · `STATUS_CHANGE` Đổi trạng thái làm việc · `IMPORT` Nhập từ Excel |
| `RetentionBasis` | `RESIGNED` Công nhân đã nghỉ (mốc: ngày chấm dứt HĐLĐ với bên cung ứng = `Employment.resign_date`, câu 44; **không** phải ngày kết thúc đợt làm việc) · `EMPLOYEE_OTHER` Công nhân lưu trữ khác · `FAILED_CANDIDATE` Ứng viên không được tuyển · `REJECTED` Hồ sơ bị từ chối · `ABANDONED` Hồ sơ bỏ dở · `CANDIDATE_OTHER` Ứng viên lưu trữ khác (thứ tự xét theo câu 2) |
| `CodeType` | `WORKER` Mã hồ sơ · `EMPLOYEE` Mã nhân viên |
| `AnonymizationKind` | `EXPIRED` Hết hạn lưu trữ · `SUBJECT_REQUEST` Theo yêu cầu của chủ thể (câu 38) |
| `AuditAction` | `CREATE` Tạo · `UPDATE` Sửa · `STATUS_CHANGE` Đổi trạng thái · `REOPEN` Mở lại hồ sơ · `VIEW_FULL_ID` Xem số CCCD đầy đủ · `VIEW_FILE` Xem tài liệu · `DOWNLOAD_FILE` Tải tài liệu · `UPLOAD_FILE` Tải lên tài liệu · `REPLACE_FILE` Thay thế tài liệu · `EXPORT` Xuất Excel · `PRINT` In báo cáo · `IMPORT` Nhập Excel · `ANONYMIZE` Ẩn danh hóa · `INTAKE_CREATE` Tạo phiên nhận diện · `INTAKE_SAVE` Lưu từ phiên nhận diện · `INTAKE_CANCEL` Hủy phiên nhận diện · `INTAKE_EXPIRE` Phiên nhận diện hết hạn · `EXTERNAL_OCR_SEND` Gửi ảnh tới API OCR · `ACCOUNT_LOCK` Khóa tài khoản · `ACCOUNT_UNLOCK` Mở khóa tài khoản · `PASSWORD_RESET` Đặt lại mật khẩu |

## 3. Model theo app

### 3.1 `apps/accounts`

**`Role`** – 4 dòng cố định, nạp bằng data migration; không có giao diện thêm/xóa.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `code` | `CharField(20, choices=RoleCode, unique)` | Có | |
| `name` | `CharField(50)` | Có | Nhãn tiếng Việt |

**`User`** – kế thừa `AbstractUser`, `AUTH_USER_MODEL = "accounts.User"`.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `username` | (sẵn có) `unique` | Có | |
| `password` | (sẵn có) | Có | PBKDF2; tối thiểu 8 ký tự, có chữ và số (validator riêng) |
| `full_name` | `CharField(100)` | Có | Hiển thị trên thanh trên |
| `role` | `FK(Role)` | Có | |
| `is_active` | (sẵn có) | Có | **Admin khóa**: `False` = khóa vô thời hạn, chỉ hết khi Admin mở khóa (câu 28) |
| `must_change_password` | `BooleanField(default=True)` | Tự động | `True` với tài khoản mẫu và sau khi Admin đặt lại mật khẩu tạm |
| `failed_login_count` | `PositiveSmallIntegerField(default=0)` | Tự động | **Khóa tạm**: đếm lần sai liên tiếp; về 0 khi đăng nhập đúng hoặc Admin mở khóa |
| `locked_until` | `DateTimeField(null)` | Tự động | **Khóa tạm**: = now + 15 phút ở lần sai thứ 5, tự hết hạn; Admin mở khóa thì xóa |
| `last_login`, `date_joined` | (sẵn có) | Tự động | |

`first_name`, `last_name`, `email`, `is_staff`, `is_superuser` của Django giữ nguyên, không dùng. Trang admin Django **không bật** (tránh đường sửa dữ liệu không qua nhật ký).

**`LoginHistory`** – chỉ thêm.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `user` | `FK(User, null)` | Không | Rỗng khi tên tài khoản không tồn tại |
| `username_attempted` | `CharField(150)` | Có | |
| `ip_address` | `GenericIPAddressField` | Có | |
| `success` | `BooleanField` | Có | |
| `failure_reason` | `CharField(100, blank)` | Không | "Sai mật khẩu", "Tài khoản đang khóa tạm", "Tài khoản bị Admin khóa" |
| `created_at` | `DateTimeField(auto_now_add)` | Tự động | |

### 3.2 `apps/audit`

**`AuditLog`** – chỉ thêm. `save()` từ chối khi bản ghi đã có `pk`; `delete()` luôn báo lỗi; QuerySet chặn `update()`/`delete()`; migration tạo trigger PostgreSQL chặn `UPDATE`/`DELETE`.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `created_at` | `DateTimeField(auto_now_add, db_index)` | Tự động | |
| `user` | `FK(User, null)` | Không | Rỗng = Hệ thống |
| `actor_label` | `CharField(150)` | Tự động | Tên tài khoản tại thời điểm ghi, hoặc "Hệ thống" |
| `action` | `CharField(30, choices=AuditAction, db_index)` | Có | |
| `object_type` | `CharField(50)` | Có | Ví dụ `workers.Worker` |
| `object_id` | `CharField(50)` | Có | |
| `object_repr` | `CharField(200)` | Có | Mã hồ sơ, mã hợp đồng, loại tài liệu, tên báo cáo. **Không chứa họ tên, số CCCD, tên tệp gốc** (câu 30) |
| `worker` | `FK(Worker, null, db_index)` | Không | Để lọc nhật ký theo hồ sơ |
| `changes` | `JSONField(default=dict)` | Không | Trường không cá nhân: `{"verification_status": ["DRAFT", "PENDING"]}`. Trường cá nhân: `{"full_name": "(xem giá trị chi tiết)"}`, giá trị nằm ở `AuditPersonalValue` |
| `ip_address` | `GenericIPAddressField(null)` | Không | |
| `note` | `TextField(blank)` | Không | Lý do, bộ lọc khi xuất báo cáo |

**`AuditPersonalValue`** – giá trị trước/sau của trường cá nhân (câu 30).

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `audit_log` | `FK(AuditLog, related_name="personal_values")` | |
| `worker` | `FK(Worker, db_index)` | Để xóa theo hồ sơ khi ẩn danh hóa |
| `field_name` | `CharField(80)` | Ví dụ `full_name`, `identity.id_number`, `emergency_contacts[2].phone`. Chỉ số trong ngoặc vuông là `pk` của dòng con (không phải `sort_order`), vì `pk` ổn định khi dòng bị xóa hoặc đổi thứ tự. Tiền tố: `identity.` (IdentityDocument), `employment.` (Employment), `emergency_contacts[pk].`, `applications[pk].`, `education[pk].`, `certificates[pk].`, `work_experiences[pk].`, `contracts[pk].`, `work_assignments[pk].`, `salary_history[pk].`; trường của chính hồ sơ không có tiền tố |
| `old_value_enc` | `EncryptedTextField(null)` | Fernet |
| `new_value_enc` | `EncryptedTextField(null)` | Fernet |

- Không có thao tác sửa. Xóa **chỉ** qua `apps.workers.retention.anonymize` (xóa mọi dòng của hồ sơ; câu 2, 30, 38). Trigger PostgreSQL của `AuditLog` giữ nguyên; `AuditPersonalValue` có trigger chặn `UPDATE`.
- Khi xem (tab Lịch sử chi tiết, trang Nhật ký; chỉ A, Q): giải mã rồi hiển thị; số định danh và CMND cũ luôn hiện dạng che; hồ sơ đã ẩn danh hiện "(đã ẩn danh)".

**Danh sách trường cá nhân** (`PERSONAL_FIELDS`, khai báo một chỗ trong `apps/audit/personal_fields.py`):

| Model | Trường |
| --- | --- |
| `Worker` | `full_name`, `date_of_birth`, `gender`, `phone`, `email`, `current_address`, `skills`, `note` |
| `IdentityDocument` | mọi trường giá trị (`id_number`, `old_id_number`, `issue_date`, `issue_place`, `expiry_date`, `hometown`, `birth_registration_place`, `permanent_address`) |
| `EmergencyContact` | `full_name`, `relationship`, `phone` |
| `Application` | `expected_salary`, `interview_notes`, `reject_reason` |
| `Education`, `Certificate`, `WorkExperience` | mọi trường chữ (`school_name`, `major`, `name`, `issuer`, `company_name`, `job_title`, `description`, `note`) |
| `Employment`, `Contract` | `resign_note`, `note` |
| `WorkAssignment` (v1.1) | `note` (công ty, vị trí, ngày không phải trường cá nhân: dùng cho thống kê) |
| `SalaryHistory` (v1.1) | `monthly_salary`, `client_unit_price`, `reason` (câu 41: giá trị lương **không** vào `AuditLog.changes`; `effective_date` không phải trường cá nhân) |

Tên logic mới ở `LOGICAL_TO_ATTR`: `monthly_salary` → `monthly_salary_enc`, `client_unit_price` → `client_unit_price_enc`.

Ghi nhật ký qua một hàm duy nhất `apps.audit.services.log(...)`, không tạo `AuditLog` trực tiếp ở view. Hàm này tự tách trường cá nhân sang `AuditPersonalValue` theo `PERSONAL_FIELDS`.

Chữ ký (đã cài ở Phase 2, `apps/audit/services.py`):

```python
log(action, *, user=None, obj=None, worker=None, changes=None, note="", request=None,
    object_type=None, object_id=None, object_repr=None)
```

- `action`: một giá trị `AuditAction`. `user = None` ghi "Hệ thống". Hàm chạy trong một giao dịch: lỗi giữa chừng thì không còn dòng nhật ký mồ côi.
- `obj`: đối tượng bị tác động; `object_type`, `object_id`, `object_repr` suy ra từ `obj` (`object_repr = str(obj)`). **`__str__` của mọi model chỉ chứa mã hoặc trường không cá nhân**, không chứa giá trị thuộc `PERSONAL_FIELDS` (có test), vì `__str__` dễ lọt vào nhật ký, log và trang lỗi.
- `object_type`, `object_id`, `object_repr`: chỉ dùng cho sự kiện **không có `obj`** (xuất báo cáo, đăng nhập...); `object_repr` là mã hoặc tên báo cáo.
- `worker`: hồ sơ liên quan; mặc định là `obj` nếu là `Worker`, hoặc `obj.worker`.
- `changes`: `{tên logic: (giá trị cũ, giá trị mới)}`, truyền **giá trị rõ**. Tên logic theo `PERSONAL_FIELDS` ở trên (`id_number`, không phải `id_number_enc`); ánh xạ sang tên cột khai báo một chỗ ở `LOGICAL_TO_ATTR` trong `apps/audit/personal_fields.py`. Tên không có trong model, hoặc trường cá nhân không gắn được với hồ sơ, thì báo `ValueError` và không ghi gì.
- **Câu 30 áp dụng cho nơi gọi:** `note` và `object_repr` do người gọi truyền (lý do, tham số lọc, tên báo cáo) **không được chứa họ tên, số CCCD, tên tệp gốc**; chỉ dùng mã hồ sơ. `log()` không tự kiểm được chuỗi tự do nên đây là quy ước bắt buộc khi viết code và khi review.

### 3.3 `apps/core`

Danh mục chung: mọi danh mục có `is_active = BooleanField(default=True)`. Mục đang được dùng thì không xóa, chỉ ngừng sử dụng; mục ngừng sử dụng không hiện trong ô chọn khi tạo mới nhưng vẫn hiện ở dữ liệu cũ.

| Model | Trường (ngoài `is_active`) | Ràng buộc |
| --- | --- | --- |
| `Department` | `name CharField(100)`, `sort_order PositiveSmallIntegerField(default=0)` | `name` unique |
| `Section` | `department FK(Department)`, `name CharField(100)`, `sort_order` | unique (`department`, `name`) |
| `Team` | `section FK(Section)`, `name CharField(100)`, `sort_order` | unique (`section`, `name`) |
| `Position` | `name CharField(100)` | `name` unique |
| `Shift` | `name CharField(50)`, `time_range CharField(20, blank)` | `name` unique |
| `ApplicationSource` | `name CharField(100)` | `name` unique |
| `EducationLevel` | `name CharField(100)`, `rank PositiveSmallIntegerField` | `name`, `rank` unique; số lớn = cao hơn (câu 14) |
| `ClientCompany` (v1.1) | `name CharField(150)`, `location CharField(100)` (tỉnh/thành, văn bản tự nhập) | unique (`name`, `location`); mỗi địa điểm một dòng (câu 39). Công ty đã có đợt làm việc thì chỉ ngừng sử dụng, không xóa. `__str__` = `"<name> – <location>"` |
| `RequiredDocumentGroup` | `name CharField(100)`, `sort_order` | `name` unique |
| `DocumentType` | `name CharField(100)`, `system_code CharField(30, null)`, `required_group FK(RequiredDocumentGroup, null)`, `sort_order` | `name` unique; `system_code` unique khi khác rỗng |

**Dữ liệu danh mục nạp sẵn** (data migration, Admin sửa được sau):

- `RequiredDocumentGroup`: CCCD mặt trước · CCCD mặt sau · Ảnh chân dung · CV hoặc Đơn xin việc (câu 4).
- `DocumentType` (`system_code` → nhóm): CCCD mặt trước (`CCCD_FRONT` → CCCD mặt trước) · CCCD mặt sau (`CCCD_BACK` → CCCD mặt sau) · Ảnh chân dung (`PORTRAIT` → Ảnh chân dung) · CV (`CV` → CV hoặc Đơn xin việc) · Đơn xin việc (`APPLICATION_LETTER` → CV hoặc Đơn xin việc) · Bằng cấp · Chứng chỉ · Hợp đồng (`CONTRACT`) · Quyết định tiếp nhận · Văn bản đồng ý xử lý dữ liệu (`CONSENT`) · **Bản cam kết** (v1.1, câu 45; không `system_code`, không thuộc nhóm bắt buộc; thêm bằng data migration mới vì các nơi đã cài đã chạy migration nạp danh mục cũ) · Khác. `system_code` không sửa được trên giao diện vì mã nguồn dùng nó (ảnh chân dung, lưu ảnh từ phiên nhận diện, tệp hợp đồng, biên bản đồng ý).
- `EducationLevel` (rank): Chưa qua đào tạo (1) · Tiểu học (2) · THCS (3) · THPT (4) · Trung cấp (5) · Cao đẳng (6) · Đại học (7) · Sau đại học (8).
- Phòng ban, bộ phận, tổ, chức danh, ca, nguồn ứng tuyển mẫu: do `seed_demo` (Phase 2) tạo, **bắt buộc** có phòng ban "Khối văn phòng" → bộ phận "Văn phòng" (câu 15); `seed_demo` v1.1 thêm vài công ty khách, đợt làm việc, lương giả và một số công nhân **không có bộ phận** để thử nhóm "Chưa có bộ phận".

**`SystemSetting`** (bảng `Settings`) – một dòng duy nhất (`pk = 1`), đọc qua `SystemSetting.load()`.

| Trường | Kiểu | Mặc định | Ghi chú |
| --- | --- | --- | --- |
| `worker_code_prefix` | `CharField(10)` | `HS` | |
| `worker_code_use_year` | `BooleanField` | `True` | `HS-2026-00123` |
| `worker_code_digits` | `PositiveSmallIntegerField` | `5` | 3–8 |
| `employee_code_prefix` | `CharField(10)` | `CN` | |
| `employee_code_use_year` | `BooleanField` | `False` | `CN-00456` |
| `employee_code_digits` | `PositiveSmallIntegerField` | `5` | 3–8 |
| `expiry_warning_days` | `PositiveSmallIntegerField` | `30` | CCCD và hợp đồng sắp hết hạn (câu 17); **dùng chung** cho đợt làm việc sắp đủ 12 tháng (câu 43) |
| `assignment_limit_months` | `PositiveSmallIntegerField` | `12` | v1.1, câu 43: số tháng của một đợt làm việc để tính cảnh báo; 1–60 **[Nội bộ]** |
| `ocr_confidence_threshold` | `PositiveSmallIntegerField` | `80` | % |
| `failed_retention_months` | `PositiveSmallIntegerField` | `12` | Câu 2 |
| `resigned_retention_years` | `PositiveSmallIntegerField` | `10` | Câu 2, câu 44: tính từ ngày chấm dứt HĐLĐ cuối cùng với bên cung ứng (`Employment.resign_date`), không từ ngày kết thúc đợt làm việc |
| `auto_archive_resigned_days` | `PositiveSmallIntegerField` | `30` | Câu 9 |
| `auto_archive_failed_days` | `PositiveSmallIntegerField` | `30` | Câu 9, quy tắc 2 và 3 |
| `stale_draft_months` | `PositiveSmallIntegerField` | `6` | Câu 9, quy tắc 4 (hồ sơ bỏ dở) |
| `intake_ttl_hours` | `PositiveSmallIntegerField` | `24` | Phiên nhận diện bỏ dở tự xóa |
| `external_ocr_enabled` | `BooleanField` | `False` | Tắt mặc định (mục V.4) |
| `external_ocr_url` | `URLField(blank)` | rỗng | Khóa API nằm trong `.env` (`EXTERNAL_OCR_API_KEY`) |
| `key_check_enc` | `EncryptedTextField(null)` | rỗng | Chuỗi cố định `PA-WORKER-KEY-CHECK` mã hóa bằng `FIELD_ENCRYPTION_KEY`. **Ghi một lần ở lần khởi động đầu, không sửa**; không hiện trên giao diện (câu 31, `kien-truc.md` mục 7) |
| `key_check_hash` | `CharField(64, null)` | rỗng | HMAC-SHA256 của cùng chuỗi bằng `HASH_KEY`. **Ghi một lần ở lần khởi động đầu, không sửa**; không hiện trên giao diện |
| `updated_by` | `FK(User, null)` | | |
| `updated_at` | `DateTimeField(auto_now)` | | |

Đổi tiền tố/số chữ số chỉ ảnh hưởng mã cấp sau đó; mã đã cấp giữ nguyên.

Các ngưỡng cố định theo yêu cầu (không cấu hình): khóa 15 phút sau 5 lần sai, tự đăng xuất sau 30 phút, tệp tối đa 10 MB. Khai báo trong `config/settings.py`.

**`CodeSequence`**

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `code_type` | `CharField(10, choices=CodeType)` | |
| `year` | `PositiveSmallIntegerField` | `0` khi mã không có năm |
| `last_number` | `PositiveIntegerField(default=0)` | Chỉ tăng |

Unique (`code_type`, `year`). Cấp mã bằng `apps.core.codes.next_code(code_type)`: `select_for_update()` dòng tương ứng trong giao dịch, `last_number += 1`, ghép chuỗi theo `SystemSetting`, **kiểm tra mã chưa tồn tại** trong `Worker.worker_code` / `Worker.employee_code`; nếu đã tồn tại thì tăng tiếp tới mã chưa dùng (câu 27). Năm lấy theo giờ Việt Nam.

Mã NV cũ từ Excel (câu 27): nhận mọi mã không trùng khớp `^[A-Za-z0-9-]{1,20}$`. Chỉ khi mã khớp định dạng đang cấu hình (`^{prefix}-\d{digits}$`, hoặc `^{prefix}-\d{4}-\d{digits}$` khi có năm) thì `last_number = max(last_number, số của mã)`; mã khác định dạng không đụng tới bộ đếm.

**`QrFormat`**

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `id_doc_type` | `CharField(20, choices=IdDocType, unique)` | Chỉ `CCCD_2021`, `CAN_CUOC_2024` (mẫu 2016 không có QR) |
| `separator` | `CharField(5)` | Mặc định `\|` |
| `field_order` | `JSONField` | Mặc định `["id_number", "old_id_number", "full_name", "date_of_birth", "gender", "permanent_address", "issue_date"]` (câu 20, **[Giả định]**) |
| `date_format` | `CharField(20)` | `ddmmyyyy` |
| `is_active` | `BooleanField` | |
| `updated_at` | `DateTimeField(auto_now)` | |

Tên trường hợp lệ trong `field_order` là danh sách cố định trong code (khớp tên trường của `Worker`/`IdentityDocument`); tên lạ hoặc `skip` thì bỏ qua phần tử đó.

### 3.4 `apps/workers`

**`Worker`**

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker_code` | `CharField(20, unique)` | Tự động | Sinh khi lưu Nháp lần đầu; không sửa |
| `employee_code` | `CharField(20, unique, null)` | Tự động | Sinh khi Tiếp nhận vào làm, hoặc nhận mã cũ từ Excel (≤ 20 ký tự, chữ/số/gạch ngang, câu 27); không sửa |
| `full_name` | `CharField(100)` | Nháp | |
| `name_search` | `CharField(100, db_index)` | Tự động | Hàm tự viết, không thêm thư viện: bỏ dấu, đ→d, chữ thường, gộp khoảng trắng; tính lại mỗi lần lưu |
| `date_of_birth` | `DateField(null, db_index)` | Gửi duyệt | < 15 tuổi: chặn lưu; 15–<18: cảnh báo (câu 16) |
| `gender` | `CharField(10, choices=Gender, blank)` | Gửi duyệt | |
| `nationality` | `CharField(50, default="Việt Nam")` | Gửi duyệt | |
| `phone` | `CharField(10, db_index)` | Nháp | Đúng 10 chữ số, bắt đầu bằng 0 |
| `email` | `EmailField(blank)` | Không | |
| `current_address` | `CharField(255, blank)` | Gửi duyệt | Nơi ở hiện tại |
| `skills` | `TextField(blank)` | Không | Câu 25 |
| `note` | `TextField(blank)` | Không | |
| `verification_status` | `CharField(20, choices=VerificationStatus, default=DRAFT, db_index)` | Tự động | Chỉ đổi qua `apps.workers.workflow` |
| `created_by` | `FK(User)` | Tự động | |
| `created_at` | `DateTimeField(auto_now_add)` | Tự động | |
| `updated_at` | `DateTimeField(db_index)` | Tự động | Cập nhật khi sửa hồ sơ **và** khi dữ liệu con thay đổi (giấy tờ, liên hệ, đồng ý, tài liệu, ứng tuyển) qua `Worker.touch()`; dùng cho quy tắc hồ sơ bỏ dở (câu 9) |
| `anonymized_at` | `DateTimeField(null)` | Tự động | Khác rỗng = đã ẩn danh hóa, không mở lại được (câu 6) |

**`IdentityDocument`** – 1-1 với `Worker`, tạo khi nhập thông tin giấy tờ lần đầu.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `OneToOneField(Worker)` | Có | |
| `id_doc_type` | `CharField(20, choices=IdDocType, blank)` | Gửi duyệt | |
| `id_number_enc` | `EncryptedTextField(null)` | Gửi duyệt | 12 chữ số. Hiển thị dạng che `0791••••2345` (câu 1) |
| `id_number_hash` | `CharField(64, unique, null)` | Tự động | HMAC của 12 chữ số; kiểm tra trùng ngay khi nhập (câu 5) |
| `old_id_number_enc` | `EncryptedTextField(null)` | Không | Số CMND cũ, 9 hoặc 12 chữ số |
| `issue_date` | `DateField(null)` | Không | Phải sau ngày sinh |
| `issue_place` | `CharField(255, blank)` | Không | |
| `expiry_date` | `DateField(null)` | Không | Dùng cho "sắp hết hạn" (danh sách việc cần làm, câu 17) |
| `hometown` | `CharField(255, blank)` | Không | Mẫu cũ; trống nếu giấy tờ không có, không suy ra |
| `birth_registration_place` | `CharField(255, blank)` | Không | Mẫu mới; trống nếu giấy tờ không có |
| `permanent_address_enc` | `EncryptedTextField(null)` | Không | |
| `updated_at` | `DateTimeField(auto_now)` | Tự động | |

Truy cập giá trị rõ chỉ qua thuộc tính có kiểm tra quyền ở tầng view; Viewer không bao giờ nhận giá trị rõ (câu 13).

**`IdentityFieldSource`** – nguồn từng trường do máy đọc (mục V).

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `worker` | `FK(Worker)` | |
| `field_name` | `CharField(50)` | `full_name`, `date_of_birth`, `gender`, `nationality`, `identity.id_number`, `identity.issue_date`… |
| `source` | `CharField(10, choices=FieldSource)` | Sửa tay sau này thì đổi thành `MANUAL` |
| `confidence` | `DecimalField(5,2, null)` | Chỉ với OCR: độ tin cậy **thấp nhất** trong các từ của trường (0–100). Trường đọc được bằng máy rồi HR sửa thì `source = MANUAL`, `edited_by_user = True`; trường máy không đọc được mà HR gõ thì `MANUAL`, `edited_by_user = False`. `confirmed_by/at` ghi cho mọi dòng khi bấm Lưu hồ sơ. Sau này `update_worker` sửa trường có dòng nguồn máy đọc cũng đổi thành `MANUAL` |
| `edited_by_user` | `BooleanField(default=False)` | HR sửa giá trị máy đọc |
| `confirmed_by` | `FK(User)` | Người xác nhận ở màn hình đối chiếu |
| `confirmed_at` | `DateTimeField` | |

Unique (`worker`, `field_name`).

**`EmergencyContact`** – ít nhất 1 dòng đủ 3 trường khi gửi duyệt.

| Trường | Kiểu | Bắt buộc |
| --- | --- | --- |
| `worker` | `FK(Worker, related_name="emergency_contacts")` | Có |
| `full_name` | `CharField(100)` | Có |
| `relationship` | `CharField(50)` | Có |
| `phone` | `CharField(10)` | Có, 10 chữ số |
| `sort_order` | `PositiveSmallIntegerField(default=0)` | Tự động |

**`DataConsent`** – lịch sử ghi nhận; bản ghi mới nhất là hiệu lực. Gửi duyệt yêu cầu bản mới nhất có `consented = True`.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker)` | Có | |
| `consented` | `BooleanField` | Có | |
| `consent_date` | `DateField` | Có | |
| `method` | `CharField(20, choices=ConsentMethod)` | Có | |
| `document` | `FK("documents.WorkerDocument", null)` | Theo điều kiện | Bắt buộc khi `method = PAPER` (tệp biên bản đã ký, loại `CONSENT`) |
| `recorded_by` | `FK(User)` | Tự động | |
| `recorded_at` | `DateTimeField(auto_now_add)` | Tự động | |

**`StatusChange`** – chỉ thêm; nguồn của dòng thời gian trạng thái (câu 11).

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker, related_name="status_changes")` | Có | |
| `from_status` | `CharField(20, choices=VerificationStatus, blank)` | Có | Trống ở dòng tạo hồ sơ |
| `to_status` | `CharField(20, choices=VerificationStatus)` | Có | |
| `reason` | `TextField(blank)` | Theo điều kiện | Xem bảng chuyển trạng thái ở mục 4. Lý do hệ thống tự điền chỉ dùng mã hồ sơ, không họ tên; ô nhập tay có gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ", không chặn lưu (câu 30) |
| `changed_by` | `FK(User, null)` | Tự động | Rỗng = Hệ thống |
| `changed_at` | `DateTimeField(auto_now_add)` | Tự động | |

**`AnonymizationRecord`** (biên bản hủy) và **`AnonymizationItem`**

| Model | Trường |
| --- | --- |
| `AnonymizationRecord` | `record_no CharField(20, unique)` dạng `BBH-2026-001`; `kind CharField(20, choices=AnonymizationKind, default=EXPIRED)`; `request_ref CharField(100, blank)` (số/ngày đơn yêu cầu, **bắt buộc** khi `kind = SUBJECT_REQUEST`); `performed_by FK(User)`; `performed_at DateTimeField(auto_now_add)`; `worker_count PositiveIntegerField`; `note TextField(blank)` (lý do; bắt buộc khi `SUBJECT_REQUEST`; không ghi họ tên) |
| `AnonymizationItem` | `record FK(AnonymizationRecord, related_name="items")`; `worker OneToOneField(Worker)` (ERD: `worker_id FK,UK`); `worker_code`, `employee_code` (chụp lại); `retention_basis CharField(choices=RetentionBasis)`; `retention_expired_on DateField` (NOT NULL, lấy từ `retention_info()`; với `SUBJECT_REQUEST` là ngày lẽ ra hết hạn, có thể ở tương lai) |

### 3.5 `apps/documents`

**`WorkerDocument`**

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker, related_name="documents")` | Có | |
| `document_type` | `FK(DocumentType)` | Có | |
| `stored_file` | `FileField(storage=PrivateStorage, null)` | Có | Rỗng sau ẩn danh hóa |
| `original_name` | `CharField(255)` | Tự động | |
| `mime_type` | `CharField(100)` | Tự động | Xác định từ chữ ký tệp (magic bytes): JPG, PNG, PDF, DOC, DOCX; đuôi tên không khớp nội dung thì từ chối |
| `size_bytes` | `PositiveIntegerField` | Tự động | ≤ 10 MB |
| `version` | `PositiveSmallIntegerField(default=1)` | Tự động | |
| `replaces` | `OneToOneField("self", null, related_name="replaced_by")` | Tự động | Bản cũ bị thay |
| `is_current` | `BooleanField(default=True, db_index)` | Tự động | Thay thế: bản cũ `False`, ẩn khỏi danh sách nhưng vẫn xem được trong lịch sử |
| `verification_status` | `CharField(20, choices=DocumentVerificationStatus, default=UNVERIFIED)` | Tự động | Đổi bởi QL/Admin |
| `verified_by` | `FK(User, null)` | Tự động | |
| `verified_at` | `DateTimeField(null)` | Tự động | |
| `note` | `TextField(blank)` | Không | |
| `uploaded_by` | `FK(User)` | Tự động | |
| `uploaded_at` | `DateTimeField(auto_now_add)` | Tự động | |

Ảnh chân dung của hồ sơ = tài liệu `is_current` mới nhất có loại `PORTRAIT` (câu 4).

### 3.6 `apps/intake`

**`IntakeSession`** – bản ghi tạm; được phép xóa cứng (không bảng nào trỏ tới).

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `id` | `UUIDField(primary_key, default=uuid4)` | Dùng trên URL |
| `created_by` | `FK(User)` | Chỉ người tạo (và Admin) mở được phiên |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `expires_at` | `DateTimeField` | `created_at + SystemSetting.intake_ttl_hours` |
| `front_image` | `FileField(storage=PrivateStorage, null)` | Thư mục `intake/<uuid>/`, tên ngẫu nhiên |
| `back_image` | `FileField(storage=PrivateStorage, null)` | |
| `cv_file` | `FileField(storage=PrivateStorage, null)` | |
| `result_enc` | `EncryptedTextField(null)` | JSON mã hóa Fernet: kết quả kiểm tra ảnh, chuỗi QR, giá trị từng trường kèm nguồn và độ tin cậy, văn bản CV |

Vòng đời (khớp `erd.md` mục 6):
- `IntakeSession.close()` xóa tệp của phiên rồi xóa dòng; gọi khi HR **hủy phiên**, mở hồ sơ cũ, hoặc phiên hết hạn. Khi HR **lưu hồ sơ** (ảnh/CV được giữ đã thành `WorkerDocument` trong cùng giao dịch) gọi `close(after_commit=True)`: dòng phiên bị xóa trong giao dịch, tệp chỉ bị xóa sau khi giao dịch thành công (lỗi giữa chừng thì phiên và ảnh còn nguyên). `get_result()`/`set_result()` đọc/ghi `result_enc` dạng JSON: `{"recognition": {doc_type, qr, quality, warnings, fields{tên: value, source, confidence, low}, timings}, "cv": {text, warnings, hints}, "doc_type_choice"}`.
- `run_daily_jobs` gọi `close()` cho mọi phiên có `expires_at < now`, ghi nhật ký `INTAKE_EXPIRE` với `actor_label = "Hệ thống"`.
- Không có trường trạng thái (tránh tạo bộ trạng thái thứ năm): phiên còn dòng nghĩa là đang mở.

### 3.7 `apps/recruitment`

**`Application`**

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker, related_name="applications")` | Có | |
| `position` | `FK(Position)` | Có | Vị trí ứng tuyển |
| `source` | `FK(ApplicationSource)` | Có | |
| `applied_date` | `DateField` | Có | |
| `expected_salary` | `DecimalField(12,0, null)` | Không | VNĐ. Từ v1.1 **mọi vai trò xem được**, kể cả Viewer (câu 48, sửa câu 13) |
| `available_date` | `DateField(null)` | Không | |
| `status` | `CharField(20, choices=RecruitmentStatus, default=NEW, db_index)` | Có | |
| `interview_at` | `DateTimeField(null)` | Theo điều kiện | Bắt buộc khi Hẹn phỏng vấn |
| `interview_notes` | `TextField(blank)` | Không | |
| `result_date` | `DateField(null)` | Theo điều kiện | Bắt buộc khi Đạt, Không đạt, Ứng viên từ chối; mặc định hôm nay |
| `reject_reason` | `TextField(blank)` | Theo điều kiện | Bắt buộc khi Không đạt |
| `created_by` | `FK(User)` | Tự động | |
| `created_at`, `updated_at` | `DateTimeField` | Tự động | |

**`Education`**: `worker FK`, `education_level FK(EducationLevel)` (Có), `school_name CharField(200)` (Có), `major CharField(200, blank)`, `start_year`, `end_year` (`PositiveSmallIntegerField(null)`), `note TextField(blank)`. Trình độ cao nhất của một người = `education_level.rank` lớn nhất (câu 14).

**`Certificate`**: `worker FK`, `name CharField(200)` (Có), `issuer CharField(200, blank)`, `issue_date DateField(null)`, `expiry_date DateField(null)`, `note TextField(blank)`.

**`WorkExperience`**: `worker FK`, `company_name CharField(200)` (Có), `job_title CharField(200, blank)`, `start_date DateField(null)`, `end_date DateField(null)`, `description TextField(blank)`.

### 3.8 `apps/employment`

**`Employment`** – thông tin làm việc hiện tại, 1-1 với `Worker`; chỉ có khi hồ sơ có mã NV.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `OneToOneField(Worker, related_name="employment")` | Có | |
| `application` | `OneToOneField(Application, null)` | Theo điều kiện | Có khi tiếp nhận từ ứng tuyển; rỗng khi nhập Excel |
| `received_date` | `DateField` | Có | Ngày tiếp nhận |
| `start_date` | `DateField` | Có | Ngày bắt đầu (= "ngày vào làm" ở danh sách) |
| `section` | `FK(Section, null)` | Không | **Từ v1.1 không bắt buộc** (câu 48, sửa câu 15). Phòng ban = `section.department`; rỗng thì chưa có phòng ban ("Chưa có bộ phận" ở báo cáo, Dashboard và bộ lọc) |
| `team` | `FK(Team, null)` | Không | Có `team` thì phải có `section` và `team` phải thuộc `section` |
| `position` | `FK(Position)` | Có | |
| `shift` | `FK(Shift, null)` | Không | |
| `manager` | `FK(Worker, null, related_name="managed_employments")` | Không | Không được là chính mình |
| `work_status` | `CharField(20, choices=WorkStatus, default=AWAITING, db_index)` | Có | |
| `resign_date` | `DateField(null)` | Theo điều kiện | Bắt buộc khi Đã nghỉ việc |
| `resign_reason` | `CharField(20, choices=ResignReason, blank)` | Theo điều kiện | Bắt buộc khi Đã nghỉ việc |
| `resign_note` | `TextField(blank)` | Không | |
| `created_at`, `updated_at` | `DateTimeField` | Tự động | |

Không sửa trực tiếp `section`, `team`, `position`, `shift`, `work_status`: mọi thay đổi đi qua `apps.employment.services.change_employment(...)`, hàm này cập nhật `Employment` và **thêm** một dòng `EmploymentHistory` (không ghi đè).

**`EmploymentHistory`** – chỉ thêm.

| Trường | Kiểu | Bắt buộc |
| --- | --- | --- |
| `worker` | `FK(Worker, related_name="employment_history")` | Có |
| `change_type` | `CharField(20, choices=EmploymentChangeType)` | Có |
| `effective_date` | `DateField` | Có |
| `decision_no` | `CharField(50, blank)` | Không |
| `reason` | `TextField(blank)` | Không |
| `from_section`, `to_section` | `FK(Section, null)` | Tự động |
| `from_team`, `to_team` | `FK(Team, null)` | Tự động |
| `from_position`, `to_position` | `FK(Position, null)` | Tự động |
| `from_shift`, `to_shift` | `FK(Shift, null)` | Tự động |
| `from_work_status`, `to_work_status` | `CharField(20, choices=WorkStatus, blank)` | Tự động |
| `created_by` | `FK(User, null)` | Tự động (rỗng = Hệ thống) |
| `created_at` | `DateTimeField(auto_now_add)` | Tự động |

**`Contract`**

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker, related_name="contracts")` | Có | |
| `contract_no` | `CharField(50, unique)` | Có | |
| `contract_type` | `CharField(20, choices=ContractType)` | Có | |
| `signed_date` | `DateField` | Có | |
| `effective_date` | `DateField` | Có | |
| `expiry_date` | `DateField(null)` | Theo điều kiện | Bắt buộc trừ `INDEFINITE`; > `effective_date` |
| `document` | `FK(WorkerDocument, null)` | Không | Tệp loại `CONTRACT` của cùng hồ sơ. Hiển thị qua `Contract.current_document`: đi theo `replaced_by` tới bản `is_current` (câu 32) |
| `note` | `TextField(blank)` | Không | |
| `created_by` | `FK(User)` | Tự động | |
| `created_at` | `DateTimeField(auto_now_add)` | Tự động | |

**Quan hệ giữa `Employment` và công ty khách hàng (v1.1):** `Employment` vẫn là quan hệ lao động giữa công nhân và **bên cung ứng** (1-1 với `Worker`): `start_date` là ngày bắt đầu với bên cung ứng, `resign_date` là ngày chấm dứt hợp đồng lao động (mốc hạn lưu trữ 10 năm, câu 44). Nơi làm việc tại công ty khách là `WorkAssignment` (1-nhiều theo thời gian). **`Section`, `Team`, `Shift`, `Department` nội bộ giữ nguyên** (quyết định 23/11/2026, câu 48): yêu cầu v1.0 còn dùng cho bộ lọc, Dashboard, báo cáo, và Phase 4 đã làm xong. Chúng mô tả bộ phận nội bộ của bên cung ứng, không mô tả nơi làm việc thực tế. **`Employment.section` đổi thành không bắt buộc** (migration ở Phase 6): form "Tiếp nhận vào làm", "Ghi nhận thay đổi" và file Excel mẫu (B3) cho phép để trống Bộ phận; có Tổ thì phải có Bộ phận; `EmploymentHistory.from_section/to_section` vốn đã cho rỗng. Việc "thay đổi bộ phận" từ rỗng sang có (hoặc ngược lại) vẫn ghi một dòng `EmploymentHistory`.

### 3.9 Đợt làm việc và lương (v1.1, `apps/employment`)

**`WorkAssignment`** – đợt làm việc của công nhân tại một công ty khách hàng (câu 40). Mỗi lúc một công nhân chỉ một công ty; giữ lịch sử, không ghi đè.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `worker` | `FK(Worker, related_name="work_assignments")` | Có | Phải có `Employment` (có mã NV) và chưa Đã nghỉ việc khi tạo mới |
| `client_company` | `FK(ClientCompany)` | Có | Đang dùng (`is_active`) khi tạo mới; đợt cũ vẫn hiện công ty đã ngừng |
| `position` | `FK(Position)` | Có | Vị trí tại công ty khách, dùng danh mục Chức danh sẵn có **[Giả định]** |
| `start_date` | `DateField` | Có | |
| `end_date` | `DateField(null)` | Không | Ngày làm cuối cùng của đợt; rỗng = đang mở. `>= start_date` |
| `note` | `TextField(blank)` | Không | Trường cá nhân (`PERSONAL_FIELDS`) |
| `created_by` | `FK(User)` | Tự động | |
| `created_at`, `updated_at` | `DateTimeField` | Tự động | |

- Ràng buộc CSDL: `CheckConstraint(end_date IS NULL OR end_date >= start_date)`; `UniqueConstraint(fields=["worker"], condition=Q(end_date__isnull=True))` (tối đa một đợt đang mở).
- Không chồng lấn ngày (đợt khác của cùng công nhân không có khoảng ngày giao nhau): kiểm tra trong `apps.employment.services` khi thêm, sửa; khóa dòng `Worker` bằng `select_for_update()` để hai người ghi cùng lúc không tạo trùng.
- Mọi thay đổi đi qua `apps.employment.services.add_assignment(...)`, `update_assignment(...)`; ghi `AuditLog` `CREATE`/`UPDATE` với `worker`. Thêm đợt mới khi đang có đợt mở: bắt buộc nhập ngày kết thúc cho đợt cũ ở cùng thao tác (đóng đợt cũ rồi mở đợt mới), hoặc báo lỗi tiếng Việt **[Nội bộ]**.
- Khi `change_employment` đổi sang Đã nghỉ việc: đợt đang mở tự có `end_date = resign_date` (ghi nhật ký `UPDATE`, người thực hiện là người đổi trạng thái) **[Nội bộ]**.
- Không có nút xóa; nhập nhầm thì sửa (giá trị cũ ghi nhật ký). **Không** thêm `TextChoices`: "Đang diễn ra" suy ra từ ngày.
- Đợt hiện tại: `start_date <= hôm nay` và (`end_date` rỗng hoặc `end_date >= hôm nay`). Đợt "sắp đủ 12 tháng" (câu 43, 48): xét **chuỗi** các đợt liền nhau cùng `client_company` (đợt sau có `start_date` không quá 1 ngày sau `end_date` đợt trước); nếu đợt hiện tại thuộc một chuỗi có `ngày đủ hạn = add_months(start_date của đợt đầu chuỗi, assignment_limit_months)` trong vòng `expiry_warning_days` ngày tới (hoặc đã qua), và `end_date` của đợt hiện tại rỗng hoặc sau `ngày đủ hạn`, thì cảnh báo **[Giả định]**; tính ở `apps.workers.indicators`, dùng `apps/core/dates.add_months`.
- `__str__` = `"Đợt làm việc <id> của <mã hồ sơ>"` (không họ tên, không lương).

**`SalaryHistory`** – lịch sử lương tháng và đơn giá tháng tính cho công ty khách (câu 41, 42). **Chỉ thêm**.

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `assignment` | `FK(WorkAssignment, related_name="salary_history")` | Có | **Câu 48:** lương và đơn giá thuộc một đợt làm việc (đơn giá phụ thuộc công ty khách); mỗi đợt có chuỗi lịch sử riêng |
| `worker` | `FK(Worker, related_name="salary_history")` | Tự động | Luôn bằng `assignment.worker` (service gán, có test); giữ để xóa theo hồ sơ khi ẩn danh hóa và truy vấn theo công nhân |
| `monthly_salary_enc` | `EncryptedTextField` | Có | Lương tháng, số nguyên VNĐ > 0, lưu chuỗi số mã hóa Fernet |
| `client_unit_price_enc` | `EncryptedTextField(null)` | Không | Đơn giá tháng tính cho công ty khách, số nguyên VNĐ > 0; rỗng = chưa có (ví dụ chưa có đợt làm việc) **[Nội bộ]** |
| `effective_date` | `DateField` | Có | Ngày áp dụng; cho phép ngày tương lai (hẹn trước); phải nằm trong khoảng ngày của đợt (`>= assignment.start_date`, và `<= assignment.end_date` nếu có) |
| `reason` | `TextField` | Có | Lý do thay đổi; dòng đầu có thể ghi "Thiết lập ban đầu". Trường cá nhân; ô nhập gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ" |
| `created_by` | `FK(User)` | Tự động | Người sửa |
| `created_at` | `DateTimeField(auto_now_add)` | Tự động | |

- Mỗi dòng là **ảnh chụp cả hai khoản** tại ngày áp dụng: đổi một khoản thì form điền sẵn khoản kia từ mức hiện tại của đợt **[Nội bộ]**; đơn giá được để trống. Mức hiện tại của một đợt = dòng của đợt có `effective_date` lớn nhất không quá hôm nay; cùng ngày thì dòng `id` lớn hơn. Lương hiện tại của công nhân = mức hiện tại của đợt hiện tại; chưa có đợt thì chưa ghi được lương.
- Sửa `start_date`/`end_date` của đợt (service `update_assignment`) bị từ chối nếu làm dòng lương của đợt nằm ngoài khoảng ngày.
- Không sửa, không xóa: `save()` từ chối khi đã có `pk`, `delete()` báo lỗi, QuerySet chặn `update()`/`delete()`; migration tạo trigger PostgreSQL chặn `UPDATE` (như `AuditPersonalValue`). **Chỉ xóa** trong `apps.workers.retention.anonymize` (câu 41, mục 4.7).
- Thêm dòng qua `apps.employment.services.add_salary(...)`: chỉ Admin và Quản lý nhân sự (kiểm tra ở máy chủ); ghi `AuditLog` `CREATE` với `worker`, giá trị lương ở `AuditPersonalValue` (`salary_history[pk].monthly_salary`, `.client_unit_price`, `.reason`).
- Mọi vai trò xem được (câu 42); xem **không** ghi nhật ký. Không có cột lương trong file xuất Excel và không nhập lương từ Excel ở v1.1.
- Thêm dòng lương: Admin, Quản lý nhân sự, trên đợt của công nhân đó (đợt đang mở hoặc đã kết thúc đều được, miễn ngày áp dụng nằm trong khoảng ngày của đợt).
- `__str__` = `"Lương <mã hồ sơ> từ dd/mm/yyyy"` (không chứa số tiền).

## 4. Quy tắc nghiệp vụ và nơi kiểm tra

Mọi quy tắc kiểm tra ở máy chủ (service/form), không chỉ ở giao diện. Mỗi quy tắc có test riêng ở phase tương ứng.

### 4.1 Chuyển trạng thái xác minh (câu 9, đã sửa ngày 21/11/2026)

Khai báo một bảng `TRANSITIONS` trong `apps/workers/workflow.py`; hàm `transition(worker, to_status, user, reason="")` là đường duy nhất đổi `verification_status`, luôn ghi `StatusChange` + `AuditLog`.

| Từ | Sang | Vai trò | Lý do | Kiểm tra thêm |
| --- | --- | --- | --- | --- |
| Nháp | Chờ duyệt | HR, QL, Admin | Không | Đủ trường "Gửi duyệt" (mục 4.3) |
| Chờ duyệt | Đã xác minh | QL, Admin | Không | Không tự duyệt (4.2) |
| Chờ duyệt | Cần bổ sung | QL, Admin | **Bắt buộc** | Không tự duyệt (4.2) |
| Chờ duyệt | Bị từ chối | QL, Admin | **Bắt buộc** | Không tự duyệt (4.2) |
| Cần bổ sung | Chờ duyệt | HR, QL, Admin | Không | Đủ trường "Gửi duyệt" |
| Đã xác minh | Chờ duyệt | Tự động | Tự điền: "Sửa trường định danh: họ tên/ngày sinh/số CCCD" | Khi lưu thay đổi `full_name`, `date_of_birth` hoặc số định danh; người sửa được ghi là người gửi duyệt lần này |
| Bị từ chối | Lưu trữ | HR, QL, Admin; Hệ thống | Không | |
| Nháp, Cần bổ sung | Lưu trữ | HR, QL, Admin; Hệ thống | Không | Hộp xác nhận |
| Đã xác minh | Lưu trữ | QL, Admin; Hệ thống | **Bắt buộc** (thủ công) | **Chặn** khi `employment.work_status` ∈ {Thử việc, Đang làm việc}. HR bị từ chối (403) |
| Lưu trữ | Nháp | HR, QL, Admin | Không | "Mở lại hồ sơ": chặn khi `anonymized_at` khác rỗng; tạo `Application` mới trạng thái Mới nộp (form hỏi vị trí, nguồn) |

Mọi cặp không có trong bảng: từ chối. Viewer: từ chối mọi chuyển.

**Cách cài ở Phase 4 (`apps/workers/workflow.py`, `rules.py`):**
- `transition(worker, to_status, user, reason, *, trigger, identity_fields, request)` khóa dòng hồ sơ (`select_for_update`), đọc lại trạng thái rồi mới kiểm tra, nên hai người bấm cùng lúc chỉ một lần thành công. `trigger` là `MANUAL` (người dùng), `SYSTEM` (tác vụ hằng ngày, `user = None`) hoặc `IDENTITY_EDIT` (sửa họ tên, ngày sinh, số CCCD khi Đã xác minh; chỉ cặp Đã xác minh → Chờ duyệt đi được bằng trigger này, không có đường thủ công).
- Hai loại lỗi: `TransitionForbidden` (sai vai trò, tự duyệt, tác nhân không được phép) → view trả 403; `TransitionError` (cặp không có trong bảng, thiếu lý do, thiếu trường gửi duyệt, đang Thử việc/Đang làm việc, đã ẩn danh) → không đổi gì, báo lỗi tiếng Việt. Thứ tự kiểm: tác nhân → vai trò → không tự duyệt → điều kiện trạng thái → lý do → trường bắt buộc.
- **Chặn Thử việc/Đang làm việc áp dụng cho MỌI đường chuyển sang Lưu trữ** (thủ công từ Nháp, Cần bổ sung, Bị từ chối, Đã xác minh và tự động), không chỉ dòng Đã xác minh: theo câu 9 (tự Lưu trữ không áp dụng cho người đang làm việc, kể cả hồ sơ nhập từ Excel đang ở Nháp) và câu 38. **[Nội bộ] cần khách xác nhận** cùng mục E của `lam-ro-yeu-cau.md`.
- Lý do hệ thống tự điền: `Sửa trường định danh: <tên trường>` (không có giá trị), `Hệ thống tự chuyển hồ sơ <mã> sang <trạng thái>`, và với tự Lưu trữ: `Tự Lưu trữ: … (hồ sơ <mã>)`, `Hồ sơ bỏ dở (hồ sơ <mã>)`. Căn cứ "Hồ sơ bỏ dở" của `retention_info` nhận ra bằng lý do bắt đầu bằng "Hồ sơ bỏ dở" **và** người thực hiện là Hệ thống.
- Ma trận 4.4 ở `apps/workers/rules.py` (`can_edit_profile`, `can_add_document`, `can_replace_document`, `can_verify_document`); hồ sơ đã ẩn danh hóa thì mọi hàm trả `False`.
- Mô-đun khác: `retention.py` (hạn lưu trữ, ẩn danh hóa), `validation.py` (kiểm tra dữ liệu dùng chung cho form và service), `services.py` (tạo, sửa, liên hệ, đồng ý, mở lại), `duplicates.py`, `indicators.py`, `listing.py`, `history_labels.py`, `apps/core/dates.py` (`add_months`, `add_years`).

### 4.2 Không tự duyệt (câu 8)
Người duyệt/trả lại/từ chối phải khác `worker.created_by` **và** khác `changed_by` của dòng `StatusChange` gần nhất có `to_status = PENDING`. Áp dụng cả với Admin.

### 4.3 Trường bắt buộc khi gửi duyệt (câu 5, mục VI)
Họ tên, SĐT (đã bắt buộc từ Nháp) + ngày sinh, giới tính, quốc tịch, nơi ở hiện tại, loại giấy tờ, số định danh, ≥ 1 người liên hệ khẩn cấp đủ 3 trường, `DataConsent` mới nhất có `consented = True`. Thiếu giấy tờ **không** chặn gửi duyệt (là chỉ số, không phải điều kiện).

### 4.4 Sửa hồ sơ theo trạng thái
| Trạng thái | Sửa thông tin cá nhân, giấy tờ, liên hệ, đồng ý | Thêm tài liệu | Thay thế tài liệu | Đổi trạng thái xác minh tài liệu |
| --- | --- | --- | --- | --- |
| Nháp, Cần bổ sung | HR, QL, Admin | HR, QL, Admin | HR, QL, Admin | QL, Admin |
| Chờ duyệt | Không ai | Không ai | Không ai | QL, Admin |
| Đã xác minh | HR, QL, Admin (sửa định danh → Chờ duyệt) | HR, QL, Admin (câu 10) | QL, Admin | QL, Admin |
| Bị từ chối | Không ai | Không ai | Không ai | Không ai |
| Lưu trữ | Không ai (chỉ xem) | Không ai | Không ai | Không ai |

Đổi trạng thái xác minh tài liệu chỉ QL, Admin (câu 34). Bị từ chối chỉ xem (câu 35). Bảng này chỉ khóa phần được duyệt; tab Tuyển dụng và Quá trình làm việc vẫn thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ (câu 36); điều này áp dụng cả cho đợt làm việc và lương (v1.1), lương chỉ A, Q thêm (câu 42).

### 4.5 Kiểm tra dữ liệu
| Quy tắc | Nơi kiểm tra | Mức |
| --- | --- | --- |
| Số định danh đúng 12 chữ số | `apps.core.validators` | Lỗi |
| Trùng số định danh (băm) | `apps.workers.duplicates.find_by_id_number` | Lỗi, kèm liên kết "Mở hồ sơ cũ" |
| Trùng SĐT, hoặc họ tên không dấu + ngày sinh (khi chưa có số định danh) | `apps.workers.duplicates.find_similar` | Cảnh báo, không chặn |
| SĐT 10 chữ số | `apps.core.validators` | Lỗi |
| Tuổi < 15 / 15–<18 | `apps.core.validators` | Lỗi / Cảnh báo |
| Ngày cấp sau ngày sinh | form `IdentityDocument` | Lỗi |
| Email đúng định dạng | `EmailField` | Lỗi |
| Tệp: định dạng thật, ≤ 10 MB | `apps.documents.validators` | Lỗi |
| **Nhập Excel – ô công thức:** chỉ báo lỗi khi ô là **công thức Excel thật** (ô có `data_type == "f"`) → "Ô không được chứa công thức Excel." Mở file bằng `openpyxl.load_workbook(..., data_only=False)`; nếu `data_only=True` thì openpyxl trả về giá trị đã tính, không phát hiện được công thức. Chữ thường bắt đầu bằng `=` `+` `-` `@` (ví dụ gạch đầu dòng "- " trong Kỹ năng, Ghi chú) vẫn nhận bình thường | `apps.reports.importer` | Lỗi dòng |
| **Nhập Excel – ô ngày kiểu Excel:** cột ngày mong đợi chuỗi `dd/mm/yyyy`; ô kiểu ngày vẫn đọc được | `apps.reports.importer` | Cảnh báo "Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại" |
| **Mọi chức năng xuất Excel (Phase 7):** luôn thêm dấu `'` trước giá trị chữ bắt đầu bằng `=` `+` `-` `@`, tab hoặc xuống dòng, qua một hàm dùng chung. Đây là **lớp bảo vệ chính** chống chèn công thức, áp dụng cho dữ liệu từ mọi nguồn (form, Excel, OCR, CV) | `apps.core.excel.safe_cell()` (xuất danh sách, báo cáo, file mẫu, biên bản) | Bắt buộc |

### 4.6 Các quy tắc khác
| Quy tắc | Nơi kiểm tra |
| --- | --- |
| Tiếp nhận vào làm: `Application.status = PASSED` **và** `Worker.verification_status = VERIFIED` (câu 7); sinh mã NV nếu chưa có, giữ mã cũ nếu đã có (câu 6); tạo/cập nhật `Employment` = Chờ nhận việc + dòng `EmploymentHistory` `ONBOARD` | `apps.employment.services.onboard` |
| Hồ sơ đủ giấy tờ: mỗi `RequiredDocumentGroup` đang dùng có ≥ 1 `WorkerDocument` `is_current` thuộc loại trong nhóm, trạng thái ≠ Không hợp lệ (câu 4) | `apps.documents.services.missing_groups` |
| Hoàn thiện = Đã xác minh và không thiếu giấy tờ | `apps.workers.indicators` |
| Sắp hết hạn: `IdentityDocument.expiry_date` hoặc `Contract.expiry_date` trong `expiry_warning_days` ngày tới | `apps.workers.indicators` |
| Tự động Lưu trữ (câu 9), 4 quy tắc: (1) Đã nghỉ việc quá `auto_archive_resigned_days` ngày kể từ `resign_date`; (2) chưa có mã NV, lần ứng tuyển gần nhất Không đạt/Ứng viên từ chối quá `auto_archive_failed_days` ngày kể từ `result_date`; (3) Bị từ chối quá `auto_archive_failed_days` ngày kể từ `StatusChange` sang Bị từ chối; (4) Nháp/Cần bổ sung có `updated_at` cũ hơn `stale_draft_months` tháng, lý do "Hồ sơ bỏ dở". Quy tắc 1–2 áp dụng cho Nháp, Cần bổ sung, Đã xác minh. Không bao giờ áp dụng cho Chờ duyệt, và **không áp dụng** khi `employment.work_status` là Thử việc hoặc Đang làm việc | `run_daily_jobs` → `apps.workers.jobs.auto_archive` |
| Hạn lưu trữ (câu 2): `retention_info(worker) -> (RetentionBasis, ngày hết hạn)` xét 6 căn cứ theo thứ tự; mốc "ngày chuyển Lưu trữ" lấy từ `StatusChange` gần nhất sang Lưu trữ. Hồ sơ Lưu trữ mà không tính được thì báo lỗi. **Test** tạo hồ sơ Lưu trữ theo đủ 6 căn cứ và qua mọi đường chuyển vào Lưu trữ (thủ công từng trạng thái, 4 quy tắc tự động, mở lại rồi lưu trữ lại), khẳng định ngày hết hạn luôn khác rỗng | `apps.workers.retention.retention_info` |
| Danh sách chờ hủy (câu 2): hồ sơ Lưu trữ, chưa ẩn danh, ngày hết hạn đã qua; có cột căn cứ lưu trữ | `apps.workers.retention.expired_queryset` |
| Ẩn danh hóa (câu 2, 30, 38): xem 4.7; xóa mọi `AuditPersonalValue` của hồ sơ, ghi 1 dòng `AuditLog` `ANONYMIZE` | `apps.workers.retention.anonymize` |
| Ẩn danh hóa theo yêu cầu (câu 38): chỉ Admin; hồ sơ `ARCHIVED`, chưa ẩn danh; bắt buộc lý do + `request_ref`; **kiểm tra mã hồ sơ gõ lại ở máy chủ**; gọi `anonymize()` với `kind = SUBJECT_REQUEST`, sinh biên bản 1 hồ sơ; biên bản ghi "Xóa sớm theo yêu cầu – lẽ ra lưu đến dd/mm/yyyy" (`AnonymizationItem.retention_expired_on`). Test: vai trò khác bị chặn, hồ sơ chưa Lưu trữ hoặc đã ẩn danh bị chặn, thiếu lý do/số đơn bị chặn, mã gõ lại sai bị chặn | `apps.workers.retention.anonymize_on_request` |
| Khóa tạm do sai mật khẩu, tự đăng xuất, buộc đổi mật khẩu | `apps.accounts` (backend + middleware) |
| Admin khóa / mở khóa (câu 28): khóa đặt `is_active = False` **và hủy mọi phiên đăng nhập đang có của người đó** (để phiên cũ không sống lại khi mở khóa); mở khóa đặt `is_active = True`, `locked_until = None`, `failed_login_count = 0` | `apps.accounts.services.lock_user`, `unlock_user` |
| Bảo vệ quyền quản trị (câu 29): Admin không tự khóa, không tự đổi vai trò; không ai khóa hoặc hạ vai trò Admin cuối cùng đang hoạt động (`role = ADMIN`, `is_active = True`). Test cho từng trường hợp | `apps.accounts.services` |
| Viewer không thấy trường nhạy cảm: số CCCD đầy đủ, CMND cũ, địa chỉ thường trú, quê quán, ảnh CCCD (câu 13). **Thay đổi v1.1 (câu 42, 48):** lương tháng, đơn giá tháng (`SalaryHistory`) và mức lương mong muốn mọi vai trò đều xem được; chỉ A, Q thêm lương. Test kỳ vọng "Viewer không thấy mức lương mong muốn" phải đổi ở Phase 6 | context của view chi tiết, danh sách, Tuyển dụng, mảnh HTMX, xuất Excel |
| Đợt làm việc (câu 40): một công ty tại một lúc, không chồng lấn, `end_date >= start_date`, công nhân có mã NV và chưa Đã nghỉ việc; nghỉ việc thì đóng đợt đang mở; sửa ngày không làm dòng lương của đợt nằm ngoài khoảng | `apps.employment.services` |
| Lương (câu 41, 42): chỉ thêm dòng mới, số nguyên VNĐ > 0, bắt buộc lý do, chỉ A, Q; mã hóa; ghi nhật ký (giá trị ở `AuditPersonalValue`) | `apps.employment.services.add_salary` |
| Đợt làm việc sắp đủ 12 tháng (câu 43, 48): trong danh sách việc cần làm ở Dashboard, dùng `expiry_warning_days` và `assignment_limit_months`; **cộng dồn chuỗi đợt liền nhau cùng công ty** (đợt sau bắt đầu không quá 1 ngày sau khi đợt trước kết thúc), tính từ `start_date` của đợt đầu chuỗi **[Giả định]**; bộ lọc `?dot_sap_du_han=1` | `apps.workers.indicators` |
| Báo cáo số công nhân đang làm theo công ty khách (câu 45): đếm đợt hiện tại theo `client_company`; bộ lọc danh sách `?cong_ty_khach=<id>` (theo đợt hiện tại) | `apps.reports`, `apps.workers.listing` |
| Hạn lưu trữ công nhân đã nghỉ (câu 44): mốc là `Employment.resign_date`, **không** dùng `WorkAssignment.end_date`. **Test:** công nhân có đợt kết thúc từ lâu nhưng chưa nghỉ việc thì `retention_info` không đổi; đổi `end_date` của đợt không làm đổi hạn lưu trữ | `apps.workers.retention.retention_info` |
| Nhập Excel v1.1 (câu 48): phần B có thêm "Công ty khách" (khớp tên + địa điểm trong `ClientCompany` đang dùng) và "Ngày bắt đầu đợt" (bắt buộc nếu có công ty khách); dòng hợp lệ tạo thêm một `WorkAssignment` (vị trí = chức danh B5); Bộ phận (B3) không bắt buộc; **không nhập lương** | `apps.reports.importer` |
| Nhập Excel (câu 27): mã NV cũ khớp `^[A-Za-z0-9-]{1,20}$`, không trùng (CSDL và trong cùng file); chỉ Admin/QL được nhập phần làm việc; danh mục khớp tên; đẩy `CodeSequence` chỉ khi mã khớp định dạng đang cấu hình (xem `CodeSequence`) | `apps.reports.importer` |
| Sinh mã (câu 6, 27): kiểm tra mã chưa tồn tại trước khi cấp, tồn tại thì tăng tiếp | `apps.core.codes.next_code` |
| Hợp đồng hiển thị tệp hiện hành (câu 32): đi theo `replaced_by` tới bản `is_current` | `Contract.current_document` |
| Lý do và mô tả nhật ký không chứa họ tên (câu 30): lý do hệ thống tự điền và `AuditLog.object_repr` chỉ dùng mã hồ sơ; ô lý do nhập tay có gợi ý, không chặn lưu | `apps.workers.workflow`, `apps.audit.services` |

### 4.7 Ẩn danh hóa giữ lại và xóa gì
| Bảng | Xóa / làm rỗng | Giữ |
| --- | --- | --- |
| `Worker` | `full_name` → "(Đã ẩn danh)", `name_search`, `date_of_birth`, `gender`, `phone`, `email`, `current_address`, `skills`, `note` | `worker_code`, `employee_code`, `verification_status` (Lưu trữ), `created_*`, đặt `anonymized_at` |
| `IdentityDocument` | Mọi trường giá trị, kể cả `id_number_hash` | Dòng khung |
| `EmergencyContact` | `full_name`, `relationship`, `phone` | Dòng khung |
| `IdentityFieldSource` | Không có giá trị cá nhân, giữ nguyên | Nguồn, độ tin cậy, người xác nhận |
| `WorkerDocument` | Tệp trên đĩa của **mọi phiên bản**, `original_name`, `note` (chữ người dùng tự gõ, có thể chứa tên; bổ sung ở Phase 4 sau rà soát) | Loại, ngày, người tải, phiên bản |
| `DataConsent` | Tệp biên bản (qua `WorkerDocument`) | Có/không, ngày, hình thức |
| `Application`, `Education`, `Certificate`, `WorkExperience` | Các trường thuộc `PERSONAL_FIELDS` (mục 3.2): `expected_salary`, `interview_notes`, `reject_reason`, tên trường/công ty/chứng chỉ, mô tả, ghi chú | Vị trí, nguồn, ngày, trạng thái, trình độ (phục vụ thống kê) |
| `Employment`, `EmploymentHistory`, `Contract` | Tệp hợp đồng, `resign_note`, `note` | Bộ phận, chức danh, ngày, trạng thái, số hợp đồng |
| `WorkAssignment` (v1.1) | `note` | Công ty khách hàng, vị trí, ngày bắt đầu/kết thúc (thống kê, không kèm tên) |
| `SalaryHistory` (v1.1) | **Xóa mọi dòng của hồ sơ** (lương tháng, đơn giá, lý do, ngày áp dụng, người sửa; xóa theo `worker`): ngoại lệ có kiểm soát của bảng chỉ thêm, chỉ trong `anonymize()` (đã ghi vào ngoại lệ "không xóa cứng" của `CLAUDE.md`) | — |
| `AuditPersonalValue` | **Xóa mọi dòng của hồ sơ** (câu 30) | — |
| `AuditLog` | Không đổi; thêm một dòng `ANONYMIZE` (`object_repr` = mã hồ sơ, `note` = số biên bản) | Toàn bộ dòng cũ: ai, khi nào, hành động, tên trường thay đổi |
| `StatusChange`, `LoginHistory` | Giữ nguyên | Toàn bộ |

Bảng này áp dụng như nhau cho cả hai loại ẩn danh hóa: hết hạn lưu trữ (`EXPIRED`, Admin duyệt từ danh sách chờ hủy) và theo yêu cầu của chủ thể (`SUBJECT_REQUEST`, câu 38). Dòng `AuditLog` `ANONYMIZE` ghi loại và số biên bản trong `note`.
