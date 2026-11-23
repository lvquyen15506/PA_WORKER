# CSDL PostgreSQL 16 của PA Worker: image chính thức, ghim digest, nâng các gói có bản vá
# bảo mật (Trivy, docs/ra-soat-bao-mat.md mục 5). Chỉ nâng đúng các gói này để không đổi
# phiên bản PostgreSQL ngoài ý muốn.
FROM postgres:16.16@sha256:3950ad7c3148ca2175ef1b6c36c9efbf78957ae8fbe8b3a5d7c35af50500382f

RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade \
        libgssapi-krb5-2 libk5crypto3 libkrb5-3 libkrb5support0 zlib1g \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm /usr/local/bin/gosu

# Chạy thẳng bằng người dùng postgres: entrypoint gốc không cần gosu để hạ quyền (gosu được
# biên dịch bằng Go cũ, có lỗ hổng thư viện chuẩn), thư mục dữ liệu vốn thuộc postgres.
USER postgres
