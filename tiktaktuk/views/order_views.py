# tiktaktuk/views/order_views.py
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from tiktaktuk.services import order as order_service
from tiktaktuk.services import user as user_service


# C - Order

def checkout_view(request, event_id):
    """Halaman Checkout — Gambar 13.1."""
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    role = user_service.get_user_role_by_session(session_id)
    if role != 'customer':
        messages.error(request, 'Hanya Customer yang dapat melakukan pemesanan.')
        return redirect('event_list')

    checkout_data = order_service.get_checkout_data(event_id)
    if not checkout_data:
        messages.error(request, 'Event tidak ditemukan.')
        return redirect('event_list')

    profile_data = user_service.get_profile_data(session_id)

    context = {
        **checkout_data,                        # event, categories, seats
        'dashboard': {'role': role},
        'username':  profile_data.get('username', ''),
        'event_id':  str(event_id),
    }
    return render(request, 'order/checkout.html', context)


def create_order_view(request, event_id):
    """POST — buat order baru. Memanggil create_order() dari service yang sudah ada."""
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method != 'POST':
        return redirect('checkout', event_id=event_id)

    # Ambil data dari form
    category_id = request.POST.get('category_id', '').strip()
    quantity_raw = request.POST.get('quantity', '1')
    seat_ids     = request.POST.getlist('seat_ids')   # list, bisa kosong
    promo_code   = request.POST.get('promo_code', '').strip() or None

    # Validasi dasar sebelum ke service
    if not category_id:
        messages.error(request, 'Pilih kategori tiket terlebih dahulu.')
        return redirect('checkout', event_id=event_id)

    try:
        quantity = int(quantity_raw)
        if quantity < 1 or quantity > 10:
            raise ValueError
    except ValueError:
        messages.error(request, 'Jumlah tiket harus antara 1 hingga 10.')
        return redirect('checkout', event_id=event_id)

    # Format items sesuai signature create_order(session_id, items, promo_code)
    items = [{
        'category_id': category_id,
        'quantity':    quantity,
        'seat_ids':    seat_ids,
    }]

    # Menangkap 2 nilai kembalian: is_success (Boolean) dan result (order_id jika sukses, teks error dari Trigger jika gagal)
    is_success, result = order_service.create_order(session_id, items, promo_code)

    if is_success:
        messages.success(request, 'Pesanan berhasil dibuat! Status: Pending.')
        return redirect('order_list')
    else:
        # Jika is_success False, tampilkan pesan error dari Trigger PostgreSQL langsung ke UI
        messages.error(request, result)
        return redirect('checkout', event_id=event_id)


def validate_promo_ajax(request):
    """
    AJAX endpoint — validasi kode promo secara real-time.
    Dipanggil dari JavaScript di checkout.html (fetch POST).
    """
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'message': 'Method tidak diizinkan.'})

    try:
        body       = json.loads(request.body)
        promo_code = body.get('promo_code', '').strip()
        price      = float(body.get('price', 0))
        quantity   = int(body.get('quantity', 1))
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'valid': False, 'message': 'Data tidak valid.'})

    if not promo_code:
        return JsonResponse({'valid': False, 'message': 'Masukkan kode promo terlebih dahulu.'})

    total_price = price * quantity
    diskon, promo_data, err = order_service.validate_promo_only(promo_code, total_price)

    if err:
        return JsonResponse({'valid': False, 'message': err})

    return JsonResponse({
        'valid':          True,
        'diskon_amount':  diskon,
        'total_after':    max(0, total_price - diskon),
        'discount_type':  promo_data['discount_type'],
        'discount_value': promo_data['discount_value'],
        'message':        'Promo berhasil diterapkan!',
    })


# R - Order

def order_list_view(request):
    """Halaman daftar order — Admin, Organizer, Customer (filtered by role)."""
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    role = user_service.get_user_role_by_session(session_id)
    if not role:
        return redirect('login')

    profile_data = user_service.get_profile_data(session_id)

    # Filter tambahan dari query string
    search        = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')

    result = order_service.get_all_orders(session_id)
    if result is None:
        messages.error(request, 'Terjadi kesalahan saat mengambil data order.')
        return redirect('dashboard')

    order_list = result.get('list_order', [])
    summary    = result.get('summary', {})

    # Filter di Python (karena query sudah ada di service)
    if search:
        order_list = [
            o for o in order_list
            if search.lower() in str(o.get('order_id', '')).lower()
        ]
    if status_filter:
        order_list = [
            o for o in order_list
            if o.get('payment_status', '').lower() == status_filter.lower()
        ]

    context = {
        'dashboard':     {'role': role},
        'username':      profile_data.get('username', ''),
        'order_list':    order_list,
        'summary':       summary,
        'search':        search,
        'status_filter': status_filter,
    }
    return render(request, 'order/order_list.html', context)


# UD - Order (Admin only)

def update_order_view(request, order_id):
    """Proses Update payment_status via Modal — hanya Admin."""
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        role = user_service.get_user_role_by_session(session_id)
        if role != 'administrator':
            messages.error(request, 'Hanya Admin yang memiliki akses.')
            return redirect('order_list')

        payment_status = request.POST.get('payment_status', '').strip()
        valid_statuses = ['Pending', 'Paid', 'Cancelled']

        if payment_status in valid_statuses:
            ok = order_service.update_order(session_id, order_id, payment_status)
            if ok:
                messages.success(request, f'Status pesanan {str(order_id)[:8]} berhasil diperbarui.')
            else:
                messages.error(request, 'Gagal memperbarui order.')
        else:
            messages.error(request, 'Status pembayaran tidak valid.')

    return redirect('order_list')


def delete_order_view(request, order_id):
    """Delete order — hanya Admin."""
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        ok = order_service.delete_order(session_id, order_id)
        if ok:
            messages.success(request, 'Order berhasil dihapus.')
        else:
            messages.error(request, 'Gagal menghapus order. Pastikan Anda adalah Admin.')

    return redirect('order_list')