-- untuk mengecek duplikasi Venue
CREATE OR REPLACE FUNCTION check_venue_duplication()
RETURNS TRIGGER AS $$
DECLARE
    existing_venue_id UUID;
BEGIN
    -- cek duplikasi (case-insensitive) untuk nama venue dan kotanya
    SELECT venue_id INTO existing_venue_id
    FROM VENUE
    WHERE LOWER(venue_name) = LOWER(NEW.venue_name)
      AND LOWER(city) = LOWER(NEW.city)
      -- jika proses UPDATE, pastikan id nya berbeda (tidak mengecek dirinya sendiri)
      AND (TG_OP = 'INSERT' OR venue_id != NEW.venue_id)
    LIMIT 1;

    -- jika ad dup, lempar error
    IF existing_venue_id IS NOT NULL THEN
        RAISE EXCEPTION 'Venue "%" di kota "%" sudah terdaftar dengan ID %.', NEW.venue_name, NEW.city, existing_venue_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_venue_duplication ON VENUE;
CREATE TRIGGER trg_check_venue_duplication
BEFORE INSERT OR UPDATE ON VENUE
FOR EACH ROW
EXECUTE FUNCTION check_venue_duplication();

-- untuk mencegah penghapusan Venue jika ada Event aktif
CREATE OR REPLACE FUNCTION check_venue_deletion()
RETURNS TRIGGER AS $$
BEGIN
    -- cek apakah terdapat event di venue ini yang jadwalnya >= waktu saat ini (belum selesai)
    IF EXISTS (
        SELECT 1 FROM EVENT
        WHERE venue_id = OLD.venue_id 
          AND event_datetime >= CURRENT_TIMESTAMP
    ) THEN
        RAISE EXCEPTION 'Venue "%" masih memiliki event aktif sehingga tidak dapat dihapus.', OLD.venue_name;
    END IF;

    -- jika tidak ada event aktif, maka dibolehkan untuk dihapus
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_venue_deletion ON VENUE;
CREATE TRIGGER trg_check_venue_deletion
BEFORE DELETE ON VENUE
FOR EACH ROW
EXECUTE FUNCTION check_venue_deletion();