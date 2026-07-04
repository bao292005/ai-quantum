---
id: SPEC-mps-defi-risk
companions: []     
sources: ["/Users/nguyenquocbao/.gemini/antigravity/brain/318a20fe-07ff-47b1-9270-05812a2f112c/briefs/brief-mps-defi-risk-20260703/brief.md"]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# QuantumRadar API

## Why

Thị trường DeFi mang rủi ro lây lan (contagion) chéo cực cao do tính lắp ghép (composability). Các quỹ Market Maker mất trắng hàng chục triệu USD khi bị thanh lý bất ngờ vì các công cụ on-chain hiện tại quá chậm hoặc liên tục báo động giả. Hệ thống này ra đời để giải quyết "nỗi đau" sinh tử đó bằng cách định lượng sự vướng víu của các giao thức thay vì biến động giá tĩnh.

## Capabilities

- **CAP-1**
  - **intent:** Hệ thống đọc dữ liệu tick-data lịch sử và real-time (từ file CSV hoặc Web3 RPC) của 3-5 giao thức L1 Ethereum (DEX, Lending, Stablecoin).
  - **success:** Có thể liên tục nạp dữ liệu vào mô hình tính toán mà không bị crash hoặc tràn bộ nhớ.
- **CAP-2**
  - **intent:** Lõi toán học PyTorch nén đồ thị bằng Kích thước Liên kết (Bond Dimension) của Matrix Product State (MPS) để tính toán Sự vướng víu (Entanglement).
  - **success:** Hệ thống lọc bỏ được 80% nhiễu thị trường (báo động giả) và xuất ra Chỉ số Mong manh (Fragility Index) từ 0-100%.
- **CAP-3**
  - **intent:** Hệ thống cung cấp API/Webhook phát đi hai cấp độ tín hiệu rủi ro: Cảnh báo Vàng (70%) và Cảnh báo Đỏ (90%).
  - **success:** Webhook gửi thành công tín hiệu JSON tới bot giao dịch mô phỏng (tốc độ < 50ms từ lúc tính toán xong).

## Constraints

- Kiến trúc **Local-First**: Toàn bộ luồng xử lý MPS phải chạy cục bộ trên môi trường CPU tiêu chuẩn, không phụ thuộc vào cụm GPU Cloud để đảm bảo chi phí (OpEx) bằng 0 trong giai đoạn PoC.
- Dữ liệu RPC phải lấy từ các nguồn miễn phí (Alchemy/Infura Free Tier) hoặc file CSV.
- Độ trễ (Latency) xử lý dữ liệu và bắn Webhook phải dưới 50ms.

## Non-goals

- Không có giao diện Dashboard phức tạp (dành cho v2).
- Không code bot tự động rút tiền cho khách hàng (Khách hàng tự code theo Webhook của hệ thống).
- Không hỗ trợ Solana hoặc Layer 2 ở phiên bản này.
- Không phát hành Token.

## Success signal

Hệ thống QuantumRadar (API) chạy thành công mô phỏng bằng dữ liệu lịch sử của sự kiện sập LUNA/UST hoặc FTX và bắn ra tín hiệu Cảnh báo Đỏ (90%) sớm ít nhất 10 phút trước khi sự cố thanh lý diện rộng xảy ra trên chuỗi.
