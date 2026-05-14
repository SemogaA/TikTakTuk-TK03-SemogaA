-- trigger utk no 4, fitur biru

-- 1. Membuat Stored Procedure untuk Fitur Biru
CREATE OR REPLACE FUNCTION validasi_penggunaan_promosi()
RETURNS TRIGGER AS $$
DECLARE
    v_promo_code VARCHAR;
    v_usage_limit INT;
    v_current_usage INT;
    v_start_date DATE;
    v_end_date DATE;
    v_event_date DATE;
BEGIN
    -- 1. Validasi Promotion saat digunakan ke sebuah Order
    -- Validasi 1: Cek apakah Promotion ID terdaftar
    SELECT promo_code, usage_limit, start_date, end_date
    INTO v_promo_code, v_usage_limit, v_start_date, v_end_date
    FROM PROMOTION
    WHERE promotion_id = NEW.promotion_id;

    IF NOT FOUND THEN
        -- PostgreSQL otomatis menambahkan awalan "ERROR: " pada RAISE EXCEPTION
        RAISE EXCEPTION 'ERROR: Promotion dengan ID % tidak ditemukan.', NEW.promotion_id;
    END IF;

    -- Validasi 2: Cek apakah penggunaan sudah mencapai usage_limit
    SELECT COUNT(*) INTO v_current_usage
    FROM ORDER_PROMOTION
    WHERE promotion_id = NEW.promotion_id;

    IF v_current_usage >= v_usage_limit THEN
        RAISE EXCEPTION 'ERROR: Promotion "%" telah mencapai batas maksimum penggunaan.', v_promo_code;
    END IF;

    -- 2. Validasi Promotion Berdasarkan Tanggal Event saat Digunakan ke Order
    -- Validasi 3: Cek apakah tanggal event berada dalam periode promo
    -- Mencari tanggal event dengan menelusuri relasi dari ORDER -> TICKET -> CATEGORY -> EVENT
    SELECT e.event_datetime::DATE INTO v_event_date
    FROM "ORDER" o
    JOIN TICKET t ON o.order_id = t.torder_id
    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
    JOIN EVENT e ON tc.tevent_id = e.event_id
    WHERE o.order_id = NEW.order_id
    LIMIT 1;

    -- Memastikan start_date <= event_date <= end_date
    IF v_event_date < v_start_date OR v_event_date > v_end_date THEN
        RAISE EXCEPTION 'ERROR: Promotion "%" tidak berlaku untuk tanggal event ini.', v_promo_code;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Membuat Trigger yang akan dipanggil sebelum data masuk ke ORDER_PROMOTION
CREATE TRIGGER trigger_cek_promosi_order
BEFORE INSERT ON ORDER_PROMOTION
FOR EACH ROW
EXECUTE FUNCTION validasi_penggunaan_promosi();