from django.shortcuts import render, redirect
from django.contrib import messages
from tiktaktuk.services import promotion as promo_service
from tiktaktuk.services import user as user_service

def promotion_list_view(request):
    session_id = request.COOKIES.get('session_id')
    role = 'guest'
    username = ''

    # Cek login dan ambil role (Jika tidak ada session, otomatis jadi Guest)
    if session_id:
        user_id = user_service.validate_session(session_id)
        if user_id:
            role = user_service.get_user_role_by_session(session_id)
            profile_data = user_service.get_profile_data(session_id)
            username = profile_data.get('username', '')

    # PROSES CREATE (Jika ada POST - Hanya Admin yang bisa)
    if request.method == 'POST':
        if role != 'administrator':
            messages.error(request, 'Akses ditolak. Hanya Admin yang dapat membuat promosi.')
            return redirect('promotion_list')

        promo_code = request.POST.get('promo_code')
        discount_type = request.POST.get('discount_type')
        discount_value = request.POST.get('discount_value')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        usage_limit = request.POST.get('usage_limit')

        new_id = promo_service.create_promotion(
            session_id, promo_code, discount_type, discount_value, 
            start_date, end_date, usage_limit
        )

        if new_id:
            messages.success(request, f'Promosi {promo_code} berhasil dibuat!')
        else:
            messages.error(request, 'Gagal membuat promosi. Pastikan kode unik dan data valid.')
        return redirect('promotion_list')

    # AMBIL PARAMETER SEARCH & FILTER
    search = request.GET.get('search', '').strip()
    type_filter = request.GET.get('type', '')

    # AMBIL DATA LIST & SUMMARY
    data = promo_service.get_all_promotions(search=search, discount_type=type_filter)

    context = {
        'summary': data['summary'],
        'promotions': data['list_promotion'],
        'dashboard': {'role': role},
        'username': username,
        'search': search,
        'type_filter': type_filter,
    }
    return render(request, 'promotion/promotion_list.html', context)

def update_promotion_view(request, promotion_id):
    session_id = request.COOKIES.get('session_id')
    if request.method == 'POST':
        ok = promo_service.update_promotion(
            session_id, promotion_id,
            request.POST.get('promo_code'),
            request.POST.get('discount_type'),
            request.POST.get('discount_value'),
            request.POST.get('start_date'),
            request.POST.get('end_date'),
            request.POST.get('usage_limit')
        )
        if ok: messages.success(request, 'Update promosi berhasil!')
        else: messages.error(request, 'Gagal update promosi.')
    return redirect('promotion_list')

def delete_promotion_view(request, promotion_id):
    session_id = request.COOKIES.get('session_id')
    if request.method == 'POST':
        ok = promo_service.delete_promotion(session_id, promotion_id)
        if ok: messages.success(request, 'Promosi berhasil dihapus.')
        else: messages.error(request, 'Gagal menghapus. Promosi mungkin sudah digunakan di transaksi.')
    return redirect('promotion_list')