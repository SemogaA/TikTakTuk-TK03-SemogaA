from django.shortcuts import render, redirect
from django.contrib import messages
from tiktaktuk.services import event as event_service
from tiktaktuk.services import user as user_service
from tiktaktuk.services import venue as venue_service
from tiktaktuk.services import artist as artist_service


def list_view(request):
    session_id = request.COOKIES.get('session_id')

    # ambil data filter dari URL
    search_query = request.GET.get('search', '')
    venue_id = request.GET.get('venue', '')
    artist_id = request.GET.get('artist', '')
    status = request.GET.get('status', 'upcoming')  # default upcoming

    events = event_service.get_events(
        search_query, venue_id if venue_id else None, artist_id if artist_id else None, status)

    venues = venue_service.get_all_venues()
    try:
        artists = artist_service.get_all_artists()
    except:
        artists = []

    context = {
        'events': events,
        'search_query': search_query,
        'selected_venue': venue_id,
        'selected_artist': artist_id,
        'selected_status': status,
        'venues': venues,
        'artists': artists,
    }

    # jika user login, tambahkan data session ke context
    if session_id:
        role = user_service.get_user_role_by_session(session_id)
        if role:
            profile_data = user_service.get_profile_data(session_id)
            context['dashboard'] = {'role': role}
            context['username'] = profile_data['username']

            if role == 'administrator':
                context['organizers'] = user_service.get_all_organizers()

    return render(request, 'event/event_list.html', context)


def create_view(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        event_title = request.POST.get('event_title')
        date = request.POST.get('date')
        time = request.POST.get('time')
        event_datetime = f"{date} {time}"
        venue_id = request.POST.get('venue_id')
        description = request.POST.get('description')
        image_url = request.POST.get('image_url', '')

        organizer_id = request.POST.get('organizer_id')

        artist_ids = request.POST.getlist('artists')
        artists = [{'artist_id': a_id, 'role': 'Main'} for a_id in artist_ids]

        tc_names = request.POST.getlist('tc_name[]')
        tc_prices = request.POST.getlist('tc_price[]')
        tc_quotas = request.POST.getlist('tc_quota[]')

        ticket_categories = []
        for n, p, q in zip(tc_names, tc_prices, tc_quotas):
            if n and p and q:
                ticket_categories.append(
                    {'category_name': n, 'price': p, 'quota': q})

        is_success, message, event_id = event_service.create_event(
            session_id, event_title, event_datetime, venue_id, description, image_url, artists, ticket_categories, organizer_id
        )

        # trigger POSTGRESQL error akan muncul di sini via messages.error
        if is_success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        return redirect('event_list')

    return redirect('event_list')


def update_view(request, event_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        event_title = request.POST.get('event_title')
        date = request.POST.get('date')
        time = request.POST.get('time')
        event_datetime = f"{date} {time}"
        venue_id = request.POST.get('venue_id')
        description = request.POST.get('description')
        image_url = request.POST.get('image_url', '')

        organizer_id = request.POST.get('organizer_id')

        artist_ids = request.POST.getlist('artists')
        artists = [{'artist_id': a_id, 'role': 'Main'} for a_id in artist_ids]

        tc_names = request.POST.getlist('tc_name[]')
        tc_prices = request.POST.getlist('tc_price[]')
        tc_quotas = request.POST.getlist('tc_quota[]')

        ticket_categories = []
        for n, p, q in zip(tc_names, tc_prices, tc_quotas):
            if n and p and q:
                ticket_categories.append(
                    {'category_name': n, 'price': p, 'quota': q})

        is_success, message = event_service.update_event(
            session_id, event_id, event_title, event_datetime, venue_id, description, image_url, artists, ticket_categories, organizer_id
        )

        # trigger POSTGRESQL error akan muncul di sini via messages.error
        if is_success:
            messages.success(request, message)
        else:
            messages.error(request, message)

    return redirect('event_list')
