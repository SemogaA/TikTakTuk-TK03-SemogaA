from django.shortcuts import render, redirect
from tiktaktuk.services import venue as venue_service


def list_view(request):
    """
    nampilin semua venue dengan fitur pencarian.
    """
    search_query = request.GET.get('search', '')
    venues = venue_service.get_all_venues(search_query)
    return render(request, 'venue_list.html', {'venues': venues, 'search_query': search_query})


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

        venue_id = venue_service.create_venue(
            session_id, venue_name, capacity, address, city, seating_type)
        if venue_id:
            return redirect('venue_list')
        else:
            return render(request, 'venue_form.html', {'error': 'gagal membuat venue. pastikan anda admin/organizer.'})

    return render(request, 'venue_form.html')


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

        success = venue_service.update_venue(
            session_id, venue_id, venue_name, capacity, address, city, seating_type)
        if success:
            return redirect('venue_list')
        else:
            venue = venue_service.get_venue_by_id(venue_id)
            return render(request, 'venue_form.html', {'venue': venue, 'error': 'gagal update venue.'})

    venue = venue_service.get_venue_by_id(venue_id)
    return render(request, 'venue_form.html', {'venue': venue})


def delete_view(request, venue_id):
    """
    pakai post untuk hapus data.
    """
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        venue_service.delete_venue(session_id, venue_id)

    return redirect('venue_list')
