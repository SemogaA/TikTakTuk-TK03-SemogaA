from django.shortcuts import render, redirect
from django.contrib import messages
from tiktaktuk.services import ticket as ticket_service
from tiktaktuk.services import user as user_service
from django.db import connection
from tiktaktuk.services.utils import dictfetchall

def _get_orders_with_event(session_id):
    """
    Ambil semua order lengkap dengan event_id untuk modal create tiket.
    get_all_orders() tidak include event_id di SELECT, jadi query sendiri.
    """
    role = user_service.get_user_role_by_session(session_id)
    from tiktaktuk.services.user import validate_session
    user_id = validate_session(session_id)
    if not user_id:
        return []

    with connection.cursor() as cursor:
        if role == 'administrator':
            cursor.execute("""
                SELECT DISTINCT
                    o.order_id, c.full_name AS customer_name,
                    e.event_title, e.event_id, v.seating_type
                FROM "ORDER" o
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                ORDER BY o.order_id;
            """)
        elif role == 'organizer':
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_res = cursor.fetchone()
            if not org_res:
                return []
            cursor.execute("""
                SELECT DISTINCT
                    o.order_id, c.full_name AS customer_name,
                    e.event_title, e.event_id, v.seating_type
                FROM "ORDER" o
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                WHERE e.organizer_id = %s
                ORDER BY o.order_id;
            """, [org_res[0]])
        else:
            return []
        return dictfetchall(cursor)


def _get_categories_with_used(session_id):
    """
    get_all_ticket_categories() tidak include field 'used'.
    Query sendiri dengan subquery hitung tiket terpakai.
    """
    role = user_service.get_user_role_by_session(session_id)
    from tiktaktuk.services.user import validate_session
    user_id = validate_session(session_id)
    if not user_id:
        return []

    with connection.cursor() as cursor:
        if role == 'administrator':
            cursor.execute("""
                SELECT tc.category_id, tc.category_name, tc.quota, tc.price, tc.tevent_id,
                       COALESCE((
                           SELECT COUNT(*) FROM TICKET t
                           JOIN "ORDER" o ON t.torder_id = o.order_id
                           WHERE t.tcategory_id = tc.category_id
                             AND o.payment_status != 'Cancelled'
                       ), 0) AS used
                FROM TICKET_CATEGORY tc
                ORDER BY tc.price ASC;
            """)
        elif role == 'organizer':
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_res = cursor.fetchone()
            if not org_res:
                return []
            cursor.execute("""
                SELECT tc.category_id, tc.category_name, tc.quota, tc.price, tc.tevent_id,
                       COALESCE((
                           SELECT COUNT(*) FROM TICKET t
                           JOIN "ORDER" o ON t.torder_id = o.order_id
                           WHERE t.tcategory_id = tc.category_id
                             AND o.payment_status != 'Cancelled'
                       ), 0) AS used
                FROM TICKET_CATEGORY tc
                JOIN EVENT e ON tc.tevent_id = e.event_id
                WHERE e.organizer_id = %s
                ORDER BY tc.price ASC;
            """, [org_res[0]])
        else:
            return []
        return dictfetchall(cursor)


def _get_available_seats_for_event(event_id):
    from django.db import connection
    from tiktaktuk.services.utils import dictfetchall

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.seat_id, s.section, s.row_number, s.seat_number, v.seating_type
            FROM SEAT s
            JOIN VENUE v ON s.venue_id = v.venue_id
            JOIN EVENT e ON e.venue_id = v.venue_id
            WHERE e.event_id = %s
            AND NOT EXISTS (
                SELECT 1
                FROM HAS_RELATIONSHIP hr
                JOIN TICKET t ON hr.ticket_id = t.ticket_id
                JOIN "ORDER" o ON t.torder_id = o.order_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                WHERE hr.seat_id = s.seat_id
                  AND tc.tevent_id = e.event_id
                  AND o.payment_status != 'Cancelled'
            )
            ORDER BY s.section, s.row_number, s.seat_number;
        """, [event_id])

        seats = dictfetchall(cursor)

        cursor.execute("""
            SELECT v.seating_type
            FROM VENUE v
            JOIN EVENT e ON e.venue_id = v.venue_id
            WHERE e.event_id = %s;
        """, [event_id])
        seating_type = cursor.fetchone()

        return {
            "seats": seats,
            "seating_type": seating_type[0] if seating_type else None
        }


def my_tickets(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    role = user_service.get_user_role_by_session(session_id)
    if not role:
        return redirect('login')

    profile_data = user_service.get_profile_data(session_id)

    data = ticket_service.get_all_tickets(session_id)
    if data is None:
        messages.error(request, 'Terjadi kesalahan saat mengambil data tiket.')
        return redirect('dashboard')

    tickets = data.get('list_ticket', [])
    summary = data.get('summary', {})

    orders = []
    categories = []
    available_seats = []
    seating_type = None

    if role in ('administrator', 'organizer'):
        orders = _get_orders_with_event(session_id)
        categories = _get_categories_with_used(session_id)
        seen_event_ids = set()
        for order in orders:
            event_id = order.get('event_id')
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            seat_data = _get_available_seats_for_event(event_id)
            for seat in seat_data.get('seats', []):
                seat['event_id'] = event_id
                available_seats.append(seat)

    context = {
        'dashboard':       {'role': role},
        'username':        profile_data.get('username', ''),
        'tickets':         tickets,
        'summary':         summary,
        'orders':          orders,
        'categories':      categories,
        'available_seats': available_seats,
        'seating_type':    seating_type,  
    }
    return render(request, 'ticket/ticket.html', context)


def create_ticket(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        order_id    = request.POST.get('order_id')
        seat_id     = request.POST.get('seat_id') or None

        print("SEAT ID DIPILIH:", seat_id)

        ticket_id, error_message = ticket_service.create_ticket(
            session_id=session_id,
            tcategory_id=category_id,
            torder_id=order_id,
            seat_id=seat_id,
        )
        if ticket_id:
            messages.success(request, 'Tiket berhasil dibuat.')
        else:
            messages.error(request, error_message or 'Gagal membuat tiket. Periksa data yang dimasukkan.')

    return redirect('my_tickets')


def update_ticket(request, ticket_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        role = user_service.get_user_role_by_session(session_id)
        if role != 'administrator':
            messages.error(request, 'Hanya Admin yang memiliki akses.')
            return redirect('my_tickets')

        status  = request.POST.get('status')
        seat_id = request.POST.get('seat_id') or None

        ok = ticket_service.update_ticket(
            session_id=session_id,
            ticket_id=ticket_id,
            status=status,
            seat_id=seat_id,
        )
        if ok:
            messages.success(request, 'Tiket berhasil diperbarui.')
        else:
            messages.error(request, 'Gagal memperbarui tiket.')

    return redirect('my_tickets')


def delete_ticket(request, ticket_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        role = user_service.get_user_role_by_session(session_id)
        if role != 'administrator':
            messages.error(request, 'Hanya Admin yang memiliki akses.')
            return redirect('my_tickets')

        ok = ticket_service.delete_ticket(
            session_id=session_id,
            ticket_id=ticket_id,
        )
        if ok:
            messages.success(request, 'Tiket berhasil dihapus.')
        else:
            messages.error(request, 'Gagal menghapus tiket.')

    return redirect('my_tickets')
