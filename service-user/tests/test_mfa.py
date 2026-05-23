@pytest.mark.unit
async def test_setup_totp_returns_provisioning_uri(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """setup/totp stores an encrypted secret, returns an otpauth:// URI and a base64 QR code."""
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post("/api/v1/auth/2fa/setup/totp")
    assert resp.status_code == 200
    body = resp.json()
    assert "provisioning_uri" in body
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    assert "qr_code_base64" in body
    # Vérifie que c'est bien du base64 décodable en PNG
    import base64
    raw = base64.b64decode(body["qr_code_base64"])
    assert raw[:4] == b"\x89PNG", "La réponse n'est pas une image PNG valide"