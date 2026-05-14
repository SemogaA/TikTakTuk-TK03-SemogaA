CREATE OR REPLACE FUNCTION check_username_validity()
RETURNS TRIGGER AS $$
BEGIN
    -- mencegah Username dengan special char (hanya boleh a-z, A-Z, 0-9)
    -- operator '!~' berarti tidak sesuai dengan regex
    IF NEW.username !~ '^[a-zA-Z0-9]+$' THEN
        RAISE EXCEPTION 'ERROR: Username "%" hanya boleh mengandung huruf dan angka tanpa simbol atau spasi.', NEW.username;
    END IF;

    -- cek username uniqueness secara case-insensitive
    -- dilakukan saat INSERT, atau saat UPDATE jika username-nya diubah (kemungkinan besar ga terjadi karena gada fitur update username)
    IF (TG_OP = 'INSERT') OR (TG_OP = 'UPDATE' AND LOWER(NEW.username) <> LOWER(OLD.username)) THEN
        IF EXISTS (
            SELECT 1 FROM USER_ACCOUNT
            WHERE LOWER(username) = LOWER(NEW.username)
        ) THEN
            RAISE EXCEPTION 'ERROR: Username "%" sudah terdaftar, gunakan username lain.', NEW.username;
        END IF;
    END IF;

    -- semua validasi lolos
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_username_validity ON USER_ACCOUNT;
CREATE TRIGGER trg_check_username_validity
BEFORE INSERT OR UPDATE ON USER_ACCOUNT
FOR EACH ROW
EXECUTE FUNCTION check_username_validity();