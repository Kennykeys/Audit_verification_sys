# Canonical Hash Specification

## Version and domain separation

The canonical format version is `audit-verification:transaction:v1`. This literal domain value is included in every serialized envelope. Plain SHA-256 provides deterministic integrity evidence only. It does not provide authenticity, secrecy, or a keyed message authentication code.

## Included fields

`transaction_id`, `amount`, `member_id`, `description`, `timestamp`, `method`, `network`, and `phone_number` are included. The timestamp is selected from `timestamp`, then `date_time`, then `created_at`.

## Excluded derived fields

`hash`, `verified`, and `status` are excluded.

## Normalization

Text uses Unicode NFC, leading and trailing whitespace is removed, and missing optional text becomes an empty string. `method` and `network` are lowercase. Amounts use finite decimal notation without insignificant trailing zeroes. Timestamps use ISO 8601 UTC with second precision and the `Z` suffix. Naive timestamps are interpreted as UTC.

## Byte-for-byte serialization

The envelope is `{"domain":"audit-verification:transaction:v1","entry":{...}}`. Serialization uses UTF-8 JSON, sorted keys, no ASCII escaping, and separators `,` and `:` with no extra whitespace. The hash is lowercase hexadecimal SHA-256 over those UTF-8 bytes.

## Golden vector

The canonical golden-vector hash is `f04946e17e0fe9dea34156936f5dbe7deb1c169d3436f81dc347e03d7192bb53`.

## Legacy compatibility

Legacy delimiter-based verification is isolated in `compute_legacy_hash` and `verify_legacy_hash`. New records must use canonical version 1 hashing. Legacy compatibility is temporary and exists only to verify pre-migration records.
