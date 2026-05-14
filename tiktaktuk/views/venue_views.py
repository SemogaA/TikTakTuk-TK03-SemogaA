from django.shortcuts import render, redirect
from django.db import DatabaseError
from django.contrib import messages
from tiktaktuk.services import venue as venue_service
from tiktaktuk.services import user as user_service


def list_view(request):
    """
    Nampilin semua venue. Semua role bisa akses, tapi tombol aksi di-handle di template.
    """
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    role = user_service.get_user_role_by_session(session_id)
    if not role:
        return redirect('login')

    search_query = request.GET.get('search', '')
    filter_city = request.GET.get('city', '')
    filter_seating = request.GET.get('seating', '')

    venues = venue_service.get_all_venues(
        search_query, filter_city, filter_seating)
    cities = venue_service.get_distinct_cities()
    profile_data = user_service.get_profile_data(session_id)

    total_venue = len(venues)
    reserved_seating = sum(
        1 for v in venues if v['seating_type'] == 'reserved')
    total_capacity = sum(v['capacity'] for v in venues)
    total_capacity_formatted = f"{total_capacity:,}".replace(',', '.')

    context = {
        'venues': venues,
        'search_query': search_query,
        'selected_city': filter_city,
        'selected_seating': filter_seating,
        'cities': cities,
        'total_venue': total_venue,
        'reserved_seating': reserved_seating,
        'total_capacity': total_capacity_formatted,
        'dashboard': {'role': role},
        'username': profile_data['username']
    }

    return render(request, 'venue/venue_list.html', context)


def create_view(request):
    """
    form untuk create venue baru.
    """
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        venue_name = request.POST.get('venue_name')
        capacity = request.POST.get('capacity')
        address = request.POST.get('address')
        city = request.POST.get('city')
        seating_type = request.POST.get('seating_type')

        try:
            venue_id = venue_service.create_venue(
                session_id, venue_name, capacity, address, city, seating_type)
            if venue_id:
                messages.success(request, 'Venue berhasil dibuat.')
            else:
                messages.error(
                    request, 'Gagal membuat venue. Pastikan Anda admin/organizer.')
        except DatabaseError as e:
            error_msg = str(e).split('\n')[0]
            messages.error(request, error_msg)

    return redirect('venue_list')


def update_view(request, venue_id):
    """
    form untuk edit data venue.
    """
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        venue_name = request.POST.get('venue_name')
        capacity = request.POST.get('capacity')
        address = request.POST.get('address')
        city = request.POST.get('city')
        seating_type = request.POST.get('seating_type')

        try:
            success = venue_service.update_venue(
                session_id, venue_id, venue_name, capacity, address, city, seating_type)
            if success:
                messages.success(request, 'Venue berhasil diupdate.')
            else:
                messages.error(request, 'Gagal update venue.')
        except DatabaseError as e:
            error_msg = str(e).split('\n')[0]
            messages.error(request, error_msg)

    return redirect('venue_list')


def delete_view(request, venue_id):
    """
    pakai post untuk hapus data.
    """
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        try:
            venue_service.delete_venue(session_id, venue_id)
            messages.success(request, 'Venue berhasil dihapus.')
        except DatabaseError as e:
            error_msg = str(e).split('\n')[0]
            messages.error(request, error_msg)

    return redirect('venue_list')
