---
title: "Product Brief: QuantumRadar"
status: "Draft"
created: "2026-07-03"
updated: "2026-07-03"
---

# Product Brief: QuantumRadar

## Executive Summary

QuantumRadar là hệ thống "Cầu dao Phân cấp" (Circuit Breaker) dành cho các quỹ Market Maker, ứng dụng lý thuyết lượng tử Matrix Product State (MPS) để dự báo đứt gãy thanh khoản chéo (cross-protocol contagion) trên DeFi. Sản phẩm này giải quyết tử huyệt của thị trường tiền mã hóa: rủi ro sụp đổ dây chuyền với tốc độ quá nhanh khiến các mô hình rủi ro hiện tại bất lực. Bằng cách định lượng Sự vướng víu (Entanglement) thay vì biến động giá tĩnh, QuantumRadar cung cấp tín hiệu rút vốn trước 10 phút, cứu vãn hàng chục triệu đô la thanh khoản cho khách hàng trước khi thảm họa xảy ra.

## The Problem

Khi thị trường biến động mạnh, rủi ro thanh lý chéo lây lan trong vài phút do tính chất lắp ghép tài chính (composability) của DeFi. Các công cụ quản trị rủi ro hiện tại (Nansen, Dune, AI Deep Learning) bị chậm hoặc báo động giả liên tục vì chỉ đo lường biến động giá cục bộ. Hậu quả là Giám đốc Rủi ro tại các quỹ MM bị mù tạm thời. Phản ứng chậm 10 phút dẫn đến thanh khoản kẹt cứng, margin call tự động, khiến quỹ bốc hơi 10-50 triệu USD.

## The Solution

Một Data Feed/Webhook tự động kích hoạt Cầu dao (Tiered Circuit Breaker). Lõi thuật toán nén đồ thị thanh khoản bằng Kích thước Liên kết (Bond Dimension) của MPS, lọc bỏ 80% nhiễu thị trường. Khi cấu trúc nợ và tài sản thế chấp giữa DEX, Lending và Stablecoin thực sự bị xé rách, hệ thống bắn tín hiệu "Rút phích cắm" trực tiếp vào bot giao dịch của Market Maker, cho phép họ hủy lệnh và bảo toàn vốn trước khi thị trường sụp đổ.

## What Makes This Different

*   **Đo lường Cấu trúc thay vì Giá:** Miễn nhiễm với các "fake pump/dump" của cá mập. Chỉ báo động khi có nguy cơ sụp đổ hệ thống.
*   **Siêu nén dữ liệu:** MPS giảm khối lượng điện toán theo cấp số nhân, cho phép xử lý toàn bộ đồ thị mạng lưới Ethereum chỉ với một server nội bộ tiêu chuẩn (độ trễ sub-millisecond).
*   **Chiến lược Local-First:** Khác với các startup dùng cloud đắt đỏ, kiến trúc này tận dụng RPC miễn phí và tính toán cục bộ, đạt chi phí vận hành (OpEx) tiệm cận 0 trong giai đoạn đầu, bảo đảm Unit Economics.

## Who This Serves

**Giám đốc Rủi ro (CRO/Risk Manager) tại Quỹ Market Maker Top-tier (quản lý >100M USD).**
Họ đã từng chịu đòn đau từ thảm họa LUNA/FTX. Họ cực đoan với rủi ro, hoài nghi với các dashboard màu mè và chỉ tin vào các tín hiệu toán học cứng rắn. Thành công đối với họ là: "Hệ thống tự động kích hoạt bot rút 15 triệu USD khỏi Aave lúc 3h sáng trước khi giao thức vỡ nợ, mà không cần tôi thức dậy bấm nút."

## Success Criteria

1.  **Độ chính xác (Accuracy):** Cảnh báo đúng sự kiện LUNA/FTX trong Backtest trước ít nhất 10 phút. Tỷ lệ báo động giả (False Positive) < 5%.
2.  **Độ trễ (Latency):** Thời gian xử lý từ khi block on-chain được tạo đến khi phát tín hiệu Webhook < 50ms.
3.  **Tỷ suất lợi nhuận (OpEx margin):** Duy trì chi phí server < $100/tháng cho 10 khách hàng đầu tiên.

## Scope (Phiên bản PoC v1.0)

**In Scope:**
*   Dữ liệu: Ethereum L1, theo dõi 3-5 giao thức cốt lõi (VD: Uniswap, Aave, MakerDAO).
*   Lõi MPS: Tính toán Chỉ số Fragility (0-100%).
*   Giao tiếp: API/Webhook gửi tín hiệu Cảnh báo Vàng (70%) và Đỏ (90%).
*   Frontend: Dashboard nội bộ (Next.js) hiển thị biểu đồ rủi ro để Demo cho khách hàng và VC.

**Out of Scope:**
*   Hỗ trợ Solana hoặc L2 (Dành cho v2).
*   Ví thông minh hoặc tự động thực thi lệnh (Bot tự rút tiền phải do khách hàng tự viết dựa trên Webhook).
*   Giao diện người dùng B2C hoặc token bán lẻ.

## Vision

Trở thành chuẩn mực "Credit Rating" và "Circuit Breaker" của toàn bộ thế giới DeFi. Khi các ngân hàng TradFi hàng nghìn tỷ đô la bước chân vào Web3 để phát hành Stablecoin hay cho vay thế chấp, QuantumRadar sẽ là lớp bảo hiểm hệ thống (Systemic Insurance Layer) bắt buộc của họ.
