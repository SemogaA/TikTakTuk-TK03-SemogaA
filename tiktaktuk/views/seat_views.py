import json
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.db import connection

from tiktaktuk.services import user as user_service 
from tiktaktuk.services.utils import dictfetchall
from tiktaktuk.services.user import validate_session, get_user_role_by_session
from tiktaktuk.services.seat import create_seat, update_seat, delete_seat


def _get_all_seats(search_query=None, venue_id=None):
    query = """
        SELECT
            s.seat_id,
            s.section,
            s.row_number,
            s.seat_number,
            s.venue_id,
            v.venue_name,
            CASE WHEN assigned.seat_id IS NOT NULL THEN 'Terisi' ELSE 'Tersedia' END AS status
        FROM SEAT s
        JOIN VENUE v ON s.venue_id = v.venue_id
        LEFT JOIN (
            SELECT DISTINCT hr.seat_id
            FROM HAS_RELATIONSHIP hr
            JOIN TICKET t ON hr.ticket_id = t.ticket_id
            JOIN "ORDER" o ON t.torder_id = o.order_id
            WHERE t.status = 'Valid' AND o.payment_status IN ('Paid', 'Pending')
        ) assigned ON s.seat_id = assigned.seat_id
    """
    filters, params = [], []
    if search_query:
        filters.append("(s.section ILIKE %s OR s.row_number ILIKE %s OR s.seat_number ILIKE %s)")
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
    if venue_id:
        filters.append("s.venue_id = %s")
        params.append(venue_id)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY v.venue_name, s.section, s.row_number, s.seat_number;"
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return dictfetchall(cursor)


def _get_seat_stats():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM SEAT;")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT hr.seat_id) 
            FROM HAS_RELATIONSHIP hr
            JOIN TICKET t ON hr.ticket_id = t.ticket_id
            JOIN "ORDER" o ON t.torder_id = o.order_id
            WHERE t.status = 'Valid' AND o.payment_status IN ('Paid', 'Pending');
        """)
        terisi = cursor.fetchone()[0]
        
    return {"total": total, "tersedia": total - terisi, "terisi": terisi}


def _get_all_venues():
    with connection.cursor() as cursor:
        cursor.execute("SELECT venue_id, venue_name FROM VENUE ORDER BY venue_name;")
        return dictfetchall(cursor)


def _get_seat_by_id(seat_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.seat_id, s.section, s.row_number, s.seat_number, s.venue_id, v.venue_name
            FROM SEAT s
            JOIN VENUE v ON s.venue_id = v.venue_id
            WHERE s.seat_id = %s;
        """, [seat_id])
        result = dictfetchall(cursor)
        return result[0] if result else None


def _is_seat_assigned(seat_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM HAS_RELATIONSHIP WHERE seat_id = %s LIMIT 1;", [seat_id])
        return cursor.fetchone() is not None


# def seat_management_page(request):
#     session_id = request.COOKIES.get("session_id")
#     user_id = validate_session(session_id)
#     role = get_user_role_by_session(session_id)

#     if not user_id:
#         return redirect("/login")

#     search_query = request.GET.get("search", "")
#     venue_filter = request.GET.get("venue_id", "")

#     seats = _get_all_seats(
#         search_query=search_query if search_query else None,
#         venue_id=venue_filter if venue_filter else None,
#     )
#     stats = _get_seat_stats()
#     venues = _get_all_venues()

#     for s in seats:
#         s['seat_id'] = str(s['seat_id'])
#         s['venue_id'] = str(s['venue_id'])
#     for v in venues:
#         v['venue_id'] = str(v['venue_id'])

#     return render(request, "seat/seat.html", {
#         "dashboard": {"role": role},
#         "seats": seats,
#         "stats": stats,
#         "venues": venues,
#         "search_query": search_query,
#         "selected_venue_id": venue_filter,
#     })

def seat_management_page(request):
    session_id = request.COOKIES.get("session_id")
    user_id = validate_session(session_id)
    role = get_user_role_by_session(session_id)

    if not user_id:
        return redirect("/login")

    # TAMBAH INI
    profile_data = user_service.get_profile_data(session_id)

    search_query = request.GET.get("search", "")
    venue_filter = request.GET.get("venue_id", "")

    seats = _get_all_seats(
        search_query=search_query if search_query else None,
        venue_id=venue_filter if venue_filter else None,
    )
    stats = _get_seat_stats()
    venues = _get_all_venues()

    for s in seats:
        s['seat_id'] = str(s['seat_id'])
        s['venue_id'] = str(s['venue_id'])
    for v in venues:
        v['venue_id'] = str(v['venue_id'])

    return render(request, "seat/seat.html", {
        "dashboard": {"role": role},
        "username": profile_data.get('username', ''),  
        "seats": seats,
        "stats": stats,
        "venues": venues,
        "search_query": search_query,
        "selected_venue_id": venue_filter,
    })

def api_create_seat(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Method tidak diizinkan."}, status=405)

    session_id = request.COOKIES.get("session_id")
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Request tidak valid."}, status=400)

    venue_id = data.get("venue_id")
    section = data.get("section", "").strip()
    row_number = data.get("row_number", "").strip()
    seat_number = data.get("seat_number", "").strip()

    if not all([venue_id, section, row_number, seat_number]):
        return JsonResponse({"success": False, "message": "Semua field wajib diisi."}, status=400)

    result = create_seat(session_id, venue_id, section, row_number, seat_number)

    if result is None:
        return JsonResponse({
            "success": False,
            "message": "Gagal menambah kursi. Pastikan venue valid dan Anda memiliki akses."
        }, status=400)

    return JsonResponse({"success": True, "message": "Kursi berhasil ditambahkan."})


def api_update_seat(request, seat_id):
    if request.method != "PUT":
        return JsonResponse({"success": False, "message": "Method tidak diizinkan."}, status=405)

    session_id = request.COOKIES.get("session_id")
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Request tidak valid."}, status=400)

    venue_id = data.get("venue_id")
    section = data.get("section", "").strip()
    row_number = data.get("row_number", "").strip()
    seat_number = data.get("seat_number", "").strip()

    if not all([venue_id, section, row_number, seat_number]):
        return JsonResponse({"success": False, "message": "Semua field wajib diisi."}, status=400)

    success = update_seat(session_id, seat_id, venue_id, section, row_number, seat_number)

    if not success:
        return JsonResponse({
            "success": False,
            "message": "Gagal memperbarui kursi. Pastikan Anda memiliki akses."
        }, status=400)

    return JsonResponse({"success": True, "message": "Kursi berhasil diperbarui."})


def api_delete_seat(request, seat_id):
    if request.method != "DELETE":
        return JsonResponse({"success": False, "message": "Method tidak diizinkan."}, status=405)

    session_id = request.COOKIES.get("session_id")

    result = delete_seat(session_id, seat_id)

    if result is True:
        return JsonResponse({"success": True, "message": "Kursi berhasil dihapus."})

    if isinstance(result, str):
        return JsonResponse({"success": False, "message": result}, status=400)

    return JsonResponse({
        "success": False,
        "message": "Gagal menghapus kursi. Pastikan Anda memiliki akses."
    }, status=400)


def api_get_seat(request, seat_id):
    if request.method != "GET":
        return JsonResponse({"success": False, "message": "Method tidak diizinkan."}, status=405)

    seat = _get_seat_by_id(seat_id)
    if not seat:
        return JsonResponse({"success": False, "message": "Kursi tidak ditemukan."}, status=404)

    seat = {k: str(v) for k, v in seat.items()}
    seat["assigned"] = _is_seat_assigned(seat_id)

    return JsonResponse({"success": True, "seat": seat})
