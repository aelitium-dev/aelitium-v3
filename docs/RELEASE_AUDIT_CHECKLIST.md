# AELITIUM — Release Audit Checklist

Purpose: ensure all public-facing surfaces remain aligned with the canonical trust boundary.

---

## 0. Context validation (MUST RUN FIRST)

hostname
pwd
git rev-parse --show-toplevel
git status --short

---

## 1. Canonical overclaim scan

grep -RIn --exclude='*.bak' \
  -e "closes the trust gap" \
  -e "no trust gap" \
  -e "captured at call time" \
  -e "after capture" \
  -e "since capture" \
  -e "at generation time" \
  -e "what the model actually" \
  -e "exactly what the model" \
  -e "verify --out" \
  README.md docs engine/capture

Expected: NO RESULTS

---

## 2. CLI command consistency

grep -RIn "verify --out" README.md docs

Expected: NO RESULTS

---

## 3. Capture adapter claims

grep -RIn "captured at call time" engine/capture

Expected: NO RESULTS

---

## 4. CLI help validation

aelitium --help
aelitium verify-bundle --help

---

## Pass criteria

- no overclaim strings
- CLI aligned
- trust boundary preserved
