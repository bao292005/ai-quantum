# Ghi chú Code Review — Story 2A.1 + 2A.2 (2026-07-26)

> Tài liệu này giải thích **dễ hiểu** các phát hiện từ code review cho bạn review sau.
> Kết luận tổng: **cả 10 acceptance criteria đều PASS**, code chạy đúng (289 test pass).
> Các mục dưới đây là **cải thiện độ bền/an toàn dữ liệu**, KHÔNG phải lỗi làm hỏng chức năng hiện tại.
>
> Mỗi mục có: *Vấn đề là gì → Ví dụ → Vì sao quan trọng → Lựa chọn xử lý → Khuyến nghị*.

Bối cảnh: 2 file model Pydantic mới —
`engine/graph/node_types.py` (Node/NodeFeatures) và `engine/graph/edge_types.py` (Edge) —
phải khớp contract JSON Schema `contracts/graph_snapshot.schema.json`.

---

## 🔧 PATCH — nên sửa (đã xác nhận bằng thực nghiệm)

### P1. Giá trị vô cực (`inf`) lọt qua validation ở các feature không giới hạn trên

**Vấn đề:** 4 feature `tvl_usd`, `volume_24h_usd`, `price_usd`, `volatility` chỉ ràng buộc `>= 0`
(không có cận trên). Pydantic **chấp nhận** `float('inf')` (vô cực dương) vì `inf >= 0` là đúng.

**Ví dụ:**
```python
NodeFeatures(tvl_usd=float('inf'), volume_24h_usd=0, price_usd=0, volatility=0, connectivity=0.5)
# → KHÔNG báo lỗi, tvl_usd = inf
```

**Vì sao quan trọng:**
- `inf` sống sót qua `model_dump()` và cả qua validator jsonschema của Python (jsonschema Python dễ dãi, coi `inf` là number).
- Nhưng khi serialize ra JSON thật: `json.dumps({"tvl_usd": float('inf')})` → sinh ra chữ `Infinity` — **KHÔNG phải JSON hợp lệ** (chuẩn JSON không có `Infinity`). Bên nhận (API, file, hệ thống khác) sẽ parse lỗi.
- `inf` lọt vào tính toán tensor (Epic 2/3) sẽ làm hỏng phép nhân ma trận (lan ra `nan`/`inf` toàn bộ).

**Lưu ý:** `nan` (not-a-number) thì **đã bị chặn sẵn** (vì `nan >= 0` là sai). Field có cận trên
(`connectivity`, `weight` với `le=1`) cũng **an toàn** vì `inf <= 1` là sai. Chỉ 4 field unbounded ở trên bị.

**Lựa chọn:**
- **(A) Sửa (khuyến nghị):** thêm `allow_inf_nan=False` vào các `Field(...)`. Pydantic sẽ reject cả `inf` lẫn `nan` một cách tường minh. Sửa ~5 dòng, thêm 1-2 test. Rủi ro gần như 0.
- (B) Bỏ qua: chấp nhận rủi ro `inf` xuất hiện nếu upstream truyền sai.

**Khuyến nghị: (A).** Đây là sửa nhỏ, an toàn, đúng tinh thần "number" của JSON Schema (JSON không có vô cực).

---

## 🤔 DECISION — cần bạn quyết định (có đánh đổi)

### D1. Pydantic tự "ép kiểu" lỏng lẻo: `True`/chuỗi `"0.5"` → số thực

**Vấn đề:** Ở chế độ mặc định (lax), Pydantic v2 tự chuyển:
- `True` → `1.0`, `False` → `0.0` (vì `bool` là con của `int` trong Python)
- chuỗi `"0.5"` → `0.5`

**Ví dụ:**
```python
NodeFeatures(tvl_usd=True, ...)     # → tvl_usd = 1.0 (không báo lỗi!)
Edge(src="a", dst="b", weight="0.5", edge_type="liquidity_flow")  # → weight = 0.5
```

**Vì sao quan trọng:** Nếu dữ liệu đầu vào bị sai kiểu (vd JSON trả về boolean thay vì số, hoặc số ở dạng chuỗi), model sẽ **âm thầm chấp nhận** thay vì báo lỗi sớm → khó phát hiện bug.

**Đánh đổi (lý do cần quyết định):** Bật chế độ chặt (`strict=True`) sẽ chặn được, **nhưng cũng chặn luôn `int → float`** hợp lệ — vd `tvl_usd=100` (số nguyên) sẽ bị từ chối, buộc mọi nơi phải truyền `100.0`. Điều này khá phiền và dễ gây lỗi ngược lại.

**Lựa chọn:**
- (A) Bật `strict=True`: an toàn kiểu tuyệt đối, nhưng caller phải luôn truyền `float`.
- **(B) Giữ lax + defer (khuyến nghị):** rủi ro thực tế thấp — kết quả ép kiểu vẫn là số thực finite hợp lệ, và round-trip qua schema vẫn đúng.
- (C) Bỏ qua hẳn.

**Khuyến nghị: (B).** Với PoC, lax tiện hơn; đánh đổi strict không đáng.

---

### D2. `metadata=None` khi `model_dump()` (không có `exclude_none`) làm hỏng round-trip

**Vấn đề:** `Edge.metadata` mặc định là `None`. Khi gọi `model_dump()` **trần** (không kèm `exclude_none=True`),
kết quả có `{"metadata": null}`. Nhưng schema định nghĩa `metadata` là kiểu `object` (không cho phép `null`)
→ validate schema **thất bại**.

**Ví dụ:**
```python
Edge(src="a", dst="b", weight=0.5, edge_type="liquidity_flow").model_dump()
# → {"src":"a","dst":"b","weight":0.5,"edge_type":"liquidity_flow","metadata": null}
#    ↑ có "metadata": null → validate_graph_snapshot() sẽ báo lỗi

# Cách đúng (test hiện tại đang dùng):
edge.model_dump(exclude_none=True)   # → bỏ metadata, schema PASS
```

**Vì sao quan trọng:** Test của chúng ta đã dùng đúng `exclude_none=True` nên PASS. Nhưng **người dùng model sau này** (Story 2A.3 Graph Builder) nếu quên `exclude_none` sẽ gặp lỗi validate khó hiểu.

**Lựa chọn:**
- (A) Thêm serializer vào model để **tự động** bỏ `metadata` khi `None` — an toàn cho mọi call-site, nhưng thêm một chút "magic" vào model.
- **(B) Giữ nguyên + ghi rõ convention "luôn dùng `model_dump(exclude_none=True)`" (khuyến nghị):** nhẹ nhàng, để consumer tự lo (giống pattern các story khác trong dự án).
- (C) Bỏ qua.

**Khuyến nghị: (B),** kèm ghi chú rõ ở Story 2A.3 khi build Graph Builder.

---

## 📦 DEFER — ghi nhận, chưa làm bây giờ (đã lưu ở `deferred-work.md`)

### DF1. `id` / `src` / `dst` chấp nhận chuỗi chỉ có khoảng trắng
`min_length=1` cho phép `" "` (một dấu cách). Đây là **giới hạn của contract** (schema cũng không có `pattern`),
không phải lỗi riêng của 2A. Sửa khi nào siết định dạng id ở schema v2.

### DF2. `metadata` không giới hạn độ sâu/kích thước giá trị
Giới hạn 32 **key** nhưng mỗi value (`Any`) có thể là dict/list lồng sâu tùy ý. Khớp với schema
(`additionalProperties: true`), downstream có quyền bỏ metadata. Chỉ cần siết nếu metadata bị lộ ra mạng.

---

## ❌ DISMISS — báo động giả (đã kiểm chứng, không phải lỗi)

| Phát hiện của reviewer | Thực tế kiểm chứng |
|---|---|
| `nan` lọt qua `ge=0` | **SAI** — Pydantic reject `nan` (vì `nan >= 0` là false) |
| `inf` lọt qua field `weight`/`connectivity` | **SAI** — `le=1` chặn `inf` |
| Edge tự nối chính nó (`src==dst`) không bị chặn | Đã được `validate_graph_snapshot()` chặn ở tầng snapshot (có test sẵn) |
| Validator metadata không chạy khi `None` | Vô hại — nhánh `if v is not None` xử lý đúng |
| Ép `True` qua đường raw dict | An toàn — jsonschema reject boolean ở đường đó |

---

## Tóm tắt hành động đề xuất

| # | Mục | Loại | Khuyến nghị |
|---|---|---|---|
| P1 | `inf` ở feature unbounded | Patch | **Sửa** (`allow_inf_nan=False`) |
| D1 | Ép kiểu lax (bool/str→float) | Decision | Giữ lax, defer |
| D2 | `metadata=None` → dump | Decision | Document convention exclude_none |
| DF1 | id/src/dst whitespace | Defer | — |
| DF2 | metadata depth | Defer | — |

**Trạng thái story 2A.1/2A.2:** để `in-progress` cho tới khi bạn review xong tài liệu này và quyết định P1/D1/D2.
Khi bạn sẵn sàng, chỉ cần nói cách xử lý từng mục, tôi sẽ áp patch.
