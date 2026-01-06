# Smart Inventory Backend

## Entities

### Inventory

* Product identified by SKU
* Stores total stock
* Available stock calculated after considering active reservations

### Reservation

* Identified by reservation_id
* Status: RESERVED | CONFIRMED | CANCELLED | EXPIRED
* expires_at = created_at + 5 minutes

## API Workflow

1. POST /inventory/reserve
   Creates idempotent TTL-based reservation when user begins checkout. Only RESERVED state blocks inventory.

2. POST /checkout/confirm
   Marks reservation CONFIRMED and makes deduction permanent.

3. POST /checkout/cancel
   Releases stock back to inventory. Operation idempotent.

4. GET /inventory/{sku}
   Returns current stock after automatic cleanup of expired carts.

## Concurrency Behavior

* First-come reservation protected using threading lock.
* If only 1 unit left and two users attempt sequentially (10:10 vs 10:11), the second user receives 409 and sees Out of stock.
* Expired carts are periodically cleaned and restored.

## Development Standards

* Single-file Flask layered separation: Controllers, Services, Repositories.
* Conventional Commits used for readable history.
* In-memory persistence acceptable as best-effort on restart.

## Notes

* Inventory never allowed to go negative.
* Duplicate requests return existing state via reservation_id.
