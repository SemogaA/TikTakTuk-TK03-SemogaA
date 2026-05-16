CREATE OR REPLACE FUNCTION cek_seat_sebelum_delete()
RETURNS TRIGGER AS $$
DECLARE
    v_section VARCHAR;
    v_row VARCHAR;
    v_seat_number VARCHAR;
BEGIN
    -- cek apakah seat dipakai
    IF EXISTS (
        SELECT 1
        FROM HAS_RELATIONSHIP
        WHERE seat_id = OLD.seat_id
    ) THEN

        SELECT section, row_number, seat_number
        INTO v_section, v_row, v_seat_number
        FROM SEAT
        WHERE seat_id = OLD.seat_id;

        RAISE EXCEPTION
        'ERROR: Kursi % - Baris % No. % tidak dapat dihapus karena sudah terisi.',
        v_section,
        v_row,
        v_seat_number;
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_cek_seat_delete ON SEAT;
CREATE TRIGGER trigger_cek_seat_delete
BEFORE DELETE ON SEAT
FOR EACH ROW
EXECUTE FUNCTION cek_seat_sebelum_delete();

CREATE OR REPLACE FUNCTION cek_quota_ticket()
RETURNS TRIGGER AS $$
DECLARE
    v_quota INT;
    v_total_ticket INT;
    v_category_name VARCHAR;
BEGIN

    SELECT quota, category_name
    INTO v_quota, v_category_name
    FROM TICKET_CATEGORY
    WHERE category_id = NEW.tcategory_id;

    SELECT COUNT(*)
    INTO v_total_ticket
    FROM TICKET t
    JOIN "ORDER" o ON t.torder_id = o.order_id
    WHERE t.tcategory_id = NEW.tcategory_id
      AND o.payment_status != 'Cancelled';

    IF v_total_ticket >= v_quota THEN
        RAISE EXCEPTION
        'ERROR: Kuota kategori tiket "%" sudah penuh. Tidak dapat membuat tiket baru.',
        v_category_name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_cek_quota_ticket ON TICKET;
CREATE TRIGGER trigger_cek_quota_ticket
BEFORE INSERT ON TICKET
FOR EACH ROW
EXECUTE FUNCTION cek_quota_ticket();