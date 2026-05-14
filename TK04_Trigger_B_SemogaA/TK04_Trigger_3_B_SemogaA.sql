-- 1. TRIGGER: Validasi Duplikasi EVENT_ARTIST
CREATE OR REPLACE FUNCTION validasi_tambah_artist_event()
RETURNS TRIGGER AS $$
DECLARE
    v_artist_name VARCHAR;
    v_event_title VARCHAR;
BEGIN
    -- Validasi 1: Cek apakah Artist terdaftar (mencegah error foreign key bawaan)
    IF NOT EXISTS(SELECT 1 FROM ARTIST WHERE artist_id = NEW.artist_id) THEN
        RAISE EXCEPTION 'ERROR: Artist dengan ID % tidak ditemukan.', NEW.artist_id;
    END IF;

    -- Validasi 2: Cek apakah Event terdaftar
    IF NOT EXISTS(SELECT 1 FROM EVENT WHERE event_id = NEW.event_id) THEN
        RAISE EXCEPTION 'ERROR: Event dengan ID % tidak ditemukan.', NEW.event_id;
    END IF;

    -- Ambil nama untuk pesan error
    SELECT name INTO v_artist_name FROM ARTIST WHERE artist_id = NEW.artist_id;
    SELECT event_title INTO v_event_title FROM EVENT WHERE event_id = NEW.event_id;

    -- Validasi 3: Cek Duplikasi
    IF EXISTS (SELECT 1 FROM EVENT_ARTIST WHERE event_id = NEW.event_id AND artist_id = NEW.artist_id) THEN
        RAISE EXCEPTION 'ERROR: Artist "%" sudah terdaftar pada event "%"', v_artist_name, v_event_title;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_cek_duplikasi_artist_event ON EVENT_ARTIST;
CREATE TRIGGER trigger_cek_duplikasi_artist_event
BEFORE INSERT ON EVENT_ARTIST
FOR EACH ROW
EXECUTE FUNCTION validasi_tambah_artist_event();

-- 2. FUNCTION: Menampilkan Sisa Kuota Kategori Tiket
CREATE OR REPLACE FUNCTION get_sisa_kuota_kategori(p_event_id UUID)
RETURNS TABLE (
    category_id UUID,
    category_name VARCHAR,
    harga NUMERIC,
    total_kuota INT,
    tiket_terjual INT,
    sisa_kuota INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tc.category_id,
        tc.category_name,
        tc.price,
        tc.quota AS total_kuota,
        -- Hitung tiket yang sudah di-generate/dibeli untuk kategori ini
        COALESCE((SELECT COUNT(*)::INT FROM TICKET t WHERE t.tcategory_id = tc.category_id), 0) AS tiket_terjual,
        -- Kurangi kuota dengan tiket terjual
        tc.quota - COALESCE((SELECT COUNT(*)::INT FROM TICKET t WHERE t.tcategory_id = tc.category_id), 0) AS sisa_kuota
    FROM TICKET_CATEGORY tc
    WHERE tc.tevent_id = p_event_id;
END;
$$ LANGUAGE plpgsql;