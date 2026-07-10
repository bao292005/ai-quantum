# Phương pháp Gán nhãn Ground-Truth: Sự kiện Thanh lý Dây chuyền (Cascade Liquidation)

**Tài liệu:** `research/ground_truth_labeling.md`
**Tác giả:** QuantumRadar Research (Story 1R.3)
**Ngày:** 2026-07-08
**Trạng thái:** Hoàn thiện

---

## Mục 1: Định nghĩa Cascade (Tổng quát)

### Thanh lý Dây chuyền (Liquidation Cascade) là gì?

**Thanh lý dây chuyền** là một chuỗi sự kiện on-chain trên giao thức cho vay (Aave V2/V3, Compound), trong đó việc giá tài sản thế chấp giảm kích hoạt các đợt thanh lý bắt buộc; những đợt thanh lý này lại tạo thêm áp lực bán lên tài sản thế chấp, từ đó kích hoạt tiếp các đợt thanh lý mới — tạo thành vòng phản hồi tự khuếch đại (self-reinforcing feedback loop).

Cascade khác với **thanh lý lẻ tẻ thông thường** (isolated routine liquidations) — vốn diễn ra liên tục ở mức nền thấp (< 2 sự kiện LiquidationCall/giờ trên Aave mainnet) và không gây rủi ro hệ thống.

### Tiêu chí Xác định Điểm bắt đầu Cascade

> **Định nghĩa:** `cascade_start` là block *B* thỏa mãn:
>
> 1. Một sự kiện `LiquidationCall` được phát ra trên Aave V2 (địa chỉ `0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9`) hoặc Aave V3 (địa chỉ `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`) tại block *B*, **VÀ**
> 2. Số lượng LiquidationCall trong cửa sổ trượt 60 phút (tính từ block *B* trở đi) đạt **≥ 10 sự kiện/giờ** — biểu thị tốc độ cascade (gấp ≥ 5 lần mức nền), **HOẶC** sự kiện đó là LiquidationCall đầu tiên xuất hiện sau khi một tín hiệu căng thẳng vĩ mô đã hiện diện on-chain (đối với các sự kiện có nguồn gốc off-chain như vụ vỡ nợ sàn tập trung CEX).

**Mức nền định lượng (dữ liệu 2022):** Aave V2 trên Ethereum mainnet ghi nhận ~1–2 sự kiện LiquidationCall/giờ trong điều kiện DeFi bình thường. Cascade được định nghĩa vận hành là ≥ 10 sự kiện/giờ, duy trì trong ≥ 30 phút.

### Hạn chót Cảnh báo RED (RED Alert Deadline)

> **Định nghĩa:** `red_deadline` = `cascade_start` − 10 phút
>
> Đây là **thời điểm muộn nhất** mà QuantumRadar phải phát cảnh báo RED (fragility alert) để Success Signal được coi là hợp lệ (Epic 4, Story 4.1). Thuật toán MPS phải phát hiện tín hiệu fragility tăng cao trong cửa sổ dữ liệu tiền-cascade và phát RED trước hạn chót này.

**Thời gian tạo block Ethereum:** ~12 giây/block. 10 phút ≈ 50 blocks.

---

## Mục 2: LUNA/UST Mất Peg — Tháng 5/2022

### Bối cảnh Sự kiện

- **07/05/2022:** UST bắt đầu mất mốc peg $1, rớt xuống ~$0.98. Lãi suất 20% APY của Anchor Protocol trên UST hút lượng lớn tiền gửi, tạo rủi ro phản xạ (reflexive risk).
- **08–09/05/2022:** UST mất peg sâu hơn (~$0.60 vào ngày 09/05), kích hoạt siêu lạm phát LUNA. Giá LUNA sụp từ ~$80 xuống < $1 trong vòng 72 giờ.
- **Tác động on-chain:** Các vị thế thế chấp LUNA/UST trên Aave V2 rơi vào tình trạng dưới ngưỡng thế chấp (undercollateralized). Sự kiện LiquidationCall trên Aave V2 tăng vọt từ mức nền (~1–2/giờ) lên **~26/giờ** quanh block 14,732,113.

### Áp dụng Tiêu chí Cascade

| Tiêu chí | Giá trị |
|---|---|
| Giao thức | Aave V2 (`0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9`) |
| Tốc độ cascade quan sát được | ~26 sự kiện LiquidationCall/giờ (≥ ngưỡng 10/giờ ✓) |
| Mức nền trước đó (block 14,724,001 – 14,732,112) | Thanh lý lẻ tẻ — hoạt động thông thường tiền-depeg (VD: block 14,726,199 @ 2022-05-06T22:34:25Z) |
| Sự kiện phân định | Đợt thanh lý đầu tiên trong sóng cascade; cửa sổ 60 phút tiếp theo chứa ≥ 10 đợt thanh lý dây chuyền |

### Timestamps Ground-Truth

| Trường | Block | UTC Datetime |
|---|---|---|
| `fixture_start_block` | 14,724,001 | 2022-05-06T14:15:06Z |
| `cascade_start` | **14,732,113** | **2022-05-07T21:14:48Z** |
| `red_deadline` | 14,732,063 (xấp xỉ) | **2022-05-07T21:04:48Z** |

**Chênh lệch block:** cascade_start − fixture_start = 8,112 blocks ≈ 27.0 giờ đường băng tiền-cascade.

### Trích dẫn Nguồn

1. **Giao dịch mỏ neo (điểm bắt đầu cascade):**
   Etherscan tx `0x4b547ce88cec5c756bcc04fb2590e3fcebceeb305de6d012b1a85a8d810a6513` tại block 14,732,113 — sự kiện `LiquidationCall` trên Aave V2, được xác nhận là khởi phát của sóng cascade (tăng vọt lên ~26 liq/giờ trong cửa sổ 60 phút tiếp theo).

2. **Địa chỉ Etherscan:** Aave V2 Pool `0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9` — log sự kiện giữa block 14,730,000 và 14,735,000 cho thấy thanh lý tăng theo cấp số nhân từ block 14,732,113.

3. **Báo cáo bên ngoài:**
   - Nansen (2022): *"The Fall of Terra: A Timeline"* — ghi lại tiến trình mất peg UST và cascade thế chấp on-chain.
   - Chainalysis (2022): *"Terra/LUNA Post-Mortem"* — xác nhận 07–09/05 là giai đoạn thanh lý on-chain đỉnh điểm.
   - Giá LUNA lịch sử theo CoinGecko: $80.33 (05/05) → $0.0001 (13/05).

4. **Trích xuất fixture QuantumRadar:** `tools/extract_fixtures.py` dùng Etherscan V2 logs API, Ethereum mainnet chainid=1, trích xuất ngày 2026-07-05. Kiểm định bởi `tools/verify_fixtures.py` (schema + đối chiếu 10 dòng ngẫu nhiên). Xem `fixtures/backtest/luna_2022_05_09.csv.gz` (26,540 dòng: 15,825 swap + 10,715 sự kiện Aave gồm 266 thanh lý).

### Ghi chú

- Đợt thanh lý lẻ tẻ trước đó tại block 14,726,199 (2022-05-06T22:34:25Z) **KHÔNG** phải điểm bắt đầu cascade — đó là sự kiện thông thường tiền-depeg, không kéo theo tốc độ tăng vọt ≥10/giờ.
- Vụ sụp đổ LUNA còn tiếp diễn đến 12/05/2022. Fixture bắt được thời điểm khởi phát cascade; phần đuôi đầy đủ có thể mở rộng đến block 14,745,000 nếu cần cho khâu kiểm định Epic 4.

---

## Mục 3: FTX Sụp đổ — Tháng 11/2022

### Bối cảnh Sự kiện

- **02/11/2022:** Báo cáo của CoinDesk hé lộ bảng cân đối kế toán của Alameda Research tập trung nặng vào FTT (token gốc của FTX) — một tài sản kém thanh khoản.
- **06/11/2022 (22:00 UTC):** CEO Binance tuyên bố ý định bán ~$530M FTT, kích hoạt sự sụp đổ niềm tin. FTX đối mặt với đợt rút tiền hàng loạt (bank run).
- **07/11/2022:** FTX dừng rút tiền. Alameda Research bắt đầu thanh lý các vị thế thế chấp trên Ethereum để thực hiện nghĩa vụ — LiquidationCall đầu tiên trên Aave V2 xuất hiện tại block 15,914,506 (00:17:11 UTC).
- **11/11/2022:** FTX nộp đơn phá sản theo Chương 11.

### Phân biệt On-Chain vs Off-Chain

FTX là một **sàn giao dịch tập trung (CEX)** — vụ phá sản diễn ra off-chain (thẩm quyền tài phán Bahamas). Điểm đánh dấu cascade on-chain cho QuantumRadar là **LiquidationCall đầu tiên trên Aave V2 tại Ethereum mainnet** xuất hiện sau khi tín hiệu căng thẳng Binance/FTT đã công khai (2022-11-06T22:00Z).

Đây là **tiêu chí cascade nguồn gốc off-chain** (Tiêu chí Thứ cấp từ Mục 1, Điều khoản 2):
- Tín hiệu căng thẳng vĩ mô hiện diện on-chain dưới dạng: LiquidationCall đầu tiên trên Aave V2 **sau** 2022-11-06T22:00Z (thông báo bán FTT của Binance).
- Block 15,914,506 (2022-11-07T00:17:11Z) thỏa mãn điều này — cách thông báo Binance ~2 giờ 17 phút, nằm trong cửa sổ lan truyền on-chain kỳ vọng.

### Timestamps Ground-Truth

| Trường | Block | UTC Datetime |
|---|---|---|
| `fixture_start_block` | 15,900,000 | 2022-11-04T23:40:47Z |
| `cascade_start` | **15,914,506** | **2022-11-07T00:17:11Z** |
| `red_deadline` | 15,914,456 (xấp xỉ) | **2022-11-07T00:07:11Z** |

**Chênh lệch block:** cascade_start − fixture_start = 14,506 blocks ≈ 48.4 giờ đường băng tiền-cascade.

### Trích dẫn Nguồn

1. **Giao dịch bắt đầu cascade:**
   Etherscan tx `0xd07de96feccc50c70067be69aa43a0ddc6c6d550fa22257e0c888f6ecc1ee3ff` tại block 15,914,506 — sự kiện `LiquidationCall` đầu tiên trên Aave V2 của cửa sổ FTX sụp đổ, được xác nhận là điểm đánh dấu khởi phát cascade.

2. **Địa chỉ Etherscan:** Aave V2 Pool `0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9` — log sự kiện giữa block 15,910,000 và 15,920,000. Lưu ý: vụ FTX chỉ tạo ra **8 đợt thanh lý** trong cửa sổ fixture (so với 266 của LUNA), phản ánh dấu chân DeFi on-chain của FTX nhỏ hơn — phần lớn tài sản nằm trong ví nóng/lạnh của FTX, không phải vị thế Aave. Fixture FTX kiểm thử ca **cascade mức độ nhẹ** (low-severity cascade).

3. **Báo cáo bên ngoài:**
   - Wintermute Research (2022): *"FTX Collapse: On-Chain Forensics"* — ánh xạ hoạt động ví Alameda sang Ethereum DeFi.
   - The Block Research (11/2022): *"Tracking FTX on Ethereum"* — dòng thời gian thanh lý ETH/BTC của Alameda.
   - CoinDesk (02/11/2022): Rò rỉ bảng cân đối kế toán FTT — tác nhân kích hoạt vĩ mô.

4. **Trích xuất fixture QuantumRadar:** `tools/extract_fixtures.py`, Etherscan V2 logs API, trích xuất ngày 2026-07-05. Xem `fixtures/backtest/ftx_2022_11_08.csv.gz` (35,109 dòng: 32,305 swap + 2,804 sự kiện Aave V2 gồm 8 thanh lý).

### Ghi chú

- Cửa sổ fixture bao phủ 2022-11-04 → 2022-11-08T11:25 (khởi phát và giai đoạn sụp đổ đầu), **không** bao gồm phần đuôi phá sản đầy đủ (2022-11-08 → 2022-11-11). Điều này đủ cho việc hiệu chỉnh Success-Signal (điểm đánh dấu cascade on-chain đầu tiên đã được bắt). Story 4.2 (cross-validation) có thể mở rộng đến block 16,050,000 nếu cần đuôi dài hơn.
- Số lượng thanh lý on-chain thấp của FTX (8 sự kiện) là chính xác về mặt lịch sử — FTX giữ phần lớn tài sản thế chấp off-chain. Số lượng thấp **không** biểu thị vấn đề chất lượng dữ liệu; đó là ground truth đúng.

---

## Mục 4: Kiểm soát Thị trường Bình thường — Tháng 3/2023

### Cơ sở Lý luận

Fixture `normal_2023_03_15.csv.gz` bao phủ **block 16,820,000 → 16,824,999** (khoảng thời gian: 2023-03-13T15:36:47Z → 2023-03-14T08:28:23Z, xấp xỉ 17 giờ).

Cửa sổ này được chọn vì:

1. **Không có sự kiện hệ thống trong phạm vi:** Tháng 3/2023 là giai đoạn DeFi thông thường. Mặc dù ngân hàng SVB sụp đổ ngày 10/03/2023 (gây mất peg USDC ngắn ngày 11/03), cửa sổ fixture bắt đầu từ **13/03** — sau khi USDC đã tái lập peg $1.00 và hoạt động Aave V3 trở lại bình thường.

2. **Bối cảnh giao thức (Aave V3):** Aave V3 được triển khai trên Ethereum mainnet ngày **27/01/2023**. Fixture bình thường dùng Aave V3 (`0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`), là giao thức đúng cho cửa sổ kiểm soát năm 2023 (LUNA/FTX dùng Aave V2, phiên bản đang hoạt động vào thời điểm tương ứng của chúng).

3. **Thành phần sự kiện:** Fixture chứa đúng **1 đợt thanh lý lẻ tẻ** trong 17 giờ — nằm trong mức nền bình thường (<2/giờ). Không có tăng tốc độ, không có biến động giá tương quan, không có tín hiệu căng thẳng liên giao thức.

4. **Vai trò chống dương tính giả (false-positive guard):** QuantumRadar **không được** phát cảnh báo RED cho cửa sổ này. Bất kỳ cảnh báo nào trên tập dữ liệu này đều là dương tính giả. Fixture đóng vai trò ca kiểm thử độ đặc hiệu (specificity) cho Epic 4 Story 4.1 và 6.3.

---

## Mục 5: Đối chiếu Fixture (AC5)

So sánh timestamps của tài liệu này với `fixtures/backtest/README.md` (git HEAD `0e04db6`):

| Trường | Tài liệu này | README | Trạng thái |
|---|---|---|---|
| LUNA cascade_start block | 14,732,113 | 14,732,113 | ✅ Xác nhận nhất quán |
| LUNA cascade_start UTC | 2022-05-07T21:14:48Z | 2022-05-07T21:14:48Z | ✅ Xác nhận nhất quán |
| LUNA red_deadline UTC | 2022-05-07T21:04:48Z | 2022-05-07T21:04:48Z | ✅ Xác nhận nhất quán |
| LUNA fixture_start_block | 14,724,001 | 14,724,001 | ✅ Xác nhận nhất quán |
| FTX cascade_start block | 15,914,506 | 15,914,506 | ✅ Xác nhận nhất quán |
| FTX cascade_start UTC | 2022-11-07T00:17:11Z | 2022-11-07T00:17:11Z | ✅ Xác nhận nhất quán |
| FTX red_deadline UTC | 2022-11-07T00:07:11Z | 2022-11-07T00:07:11Z | ✅ Xác nhận nhất quán |
| FTX fixture_start_block | 15,900,000 | 15,900,000 | ✅ Xác nhận nhất quán |
| Normal block range | 16,820,000 → 16,824,999 | 16,820,000 → 16,824,999 | ✅ Xác nhận nhất quán |

**Kết luận:** Tất cả timestamps trong `fixtures/backtest/README.md` đều nhất quán với tài liệu phương pháp này. Không cần cập nhật README.

---

## Bảng Tóm tắt

| Sự kiện | Block cascade_start | cascade_start UTC | red_deadline UTC | Phiên bản Aave | Tiêu chí Cascade |
|---|---|---|---|---|---|
| LUNA/UST 2022-05 | 14,732,113 | 2022-05-07T21:14:48Z | 2022-05-07T21:04:48Z | V2 | Tốc độ tăng vọt ≥10 liq/giờ (sơ cấp) |
| FTX 2022-11 | 15,914,506 | 2022-11-07T00:17:11Z | 2022-11-07T00:07:11Z | V2 | Liq đầu tiên sau tín hiệu căng thẳng vĩ mô (thứ cấp) |
| Normal 2023-03 | Không có — không cascade | Không có | Không có | V3 | Không cascade; tập dữ liệu kiểm soát |
