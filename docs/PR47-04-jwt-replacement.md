# PR47-04 — JWT/ECDSA Replacement (Already Complete)

**Status:** ✅ Complete  
**Date:** 2026-11-01

## Summary

Migration from vulnerable `python-jose` (ECDSA) to `PyJWT` with HS256 algorithm is **already fully implemented** in the codebase.

## Implementation Details

### JWT Library
- **Current:** PyJWT 2.15.0+ with `crypto` extras
- **Algorithm:** HS256 (HMAC-SHA256, pinned in code)
- **No references to:** python-jose, ecdsa, or other vulnerable crypto libs

### Implementation Location
- **Main service:** `src/infrastructure/auth/jwt.py`
- **Algorithm constant:** `JWT_ALGORITHM = "HS256"` (line 11)
- **Token creation:** `JwtAccessTokenService.create_access_token()`
- **Token validation:** `JwtAccessTokenService.decode_token()`

### Verified Tests (9 passing)

1. ✅ **Access token round-trip uses HS256**
   - Token created with HS256
   - Token decoded successfully
   
2. ✅ **HS256 algorithm is pinned and enforced**
   - Only HS256 accepted in header
   - Other algorithms (HS384, HS512) rejected
   
3. ✅ **Token rejection cases:**
   - Expired tokens → `UnauthorizedError`
   - Invalid signature → `UnauthorizedError`
   - Unexpected algorithm → `UnauthorizedError`
   - Missing subject (`sub` claim) → `UnauthorizedError`
   - Missing expiration (`exp` claim) → `UnauthorizedError`
   
4. ✅ **Audience claim handling:**
   - JWT_AUD_WEB and JWT_AUD_GATEWAY supported
   - Claims correctly included and verified

### CI/CD Status
- ✅ No ECDSA ignore flags in pip-audit
- ✅ All security scanning passes
- ✅ No deprecated crypto dependencies

## Test Evidence

```
tests/unit/auth/test_jwt.py::test_access_token_round_trip_uses_hs256 PASSED
tests/unit/auth/test_jwt.py::test_access_token_includes_audience_claim PASSED
tests/unit/auth/test_jwt.py::test_access_token_rejects_expired_token PASSED
tests/unit/auth/test_jwt.py::test_access_token_rejects_invalid_signature PASSED
tests/unit/auth/test_jwt.py::test_access_token_rejects_unexpected_algorithm PASSED
tests/unit/auth/test_jwt.py::test_access_token_rejects_missing_subject PASSED
tests/unit/auth/test_jwt.py::test_access_token_rejects_missing_expiration PASSED
tests/unit/auth/test_jwt_algorithm.py::test_access_tokens_are_issued_with_pinned_hs256_algorithm PASSED
tests/unit/auth/test_jwt_algorithm.py::test_access_token_decoder_rejects_a_different_algorithm PASSED

======================= 9 passed in 3.52s =======================
```

## Dependency Status

**pyproject.toml:**
```toml
PyJWT = { version = ">=2.15.0", extras = ["crypto"] }
```

**Removed:**
- python-jose (never installed)
- ecdsa (never installed)

## Security Checks Passed

- ✅ No python-jose imports
- ✅ No ecdsa imports
- ✅ HS256 algorithm hardcoded (no negotiation)
- ✅ All required claims validated (exp, sub)
- ✅ Invalid algorithms rejected
- ✅ Signature verification enabled
- ✅ pip-audit clean (no ECDSA ignore needed)

## Conclusion

**No action needed** — PR47-04 requirements are fully met. Migration to PyJWT HS256 is complete and thoroughly tested.

Next: **PR47-05 (Immutable images)**
