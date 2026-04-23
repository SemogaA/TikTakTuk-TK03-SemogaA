from django.shortcuts import render, redirect
from tiktaktuk.services import artist as artist_service


def list_view(request):
    artists = artist_service.get_all_artists()
    return render(request, 'artist_list.html', {'artists': artists})


def create_view(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name')
        genre = request.POST.get('genre')

        artist_id = artist_service.create_artist(session_id, name, genre)
        if artist_id:
            return redirect('artist_list')
        else:
            return render(request, 'artist_form.html', {'error': 'gagal membuat artis.'})

    return render(request, 'artist_form.html')


def update_view(request, artist_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name')
        genre = request.POST.get('genre')

        success = artist_service.update_artist(
            session_id, artist_id, name, genre)
        if success:
            return redirect('artist_list')
        else:
            artist = artist_service.get_artist_by_id(artist_id)
            return render(request, 'artist_form.html', {'artist': artist, 'error': 'gagal update artis.'})

    artist = artist_service.get_artist_by_id(artist_id)
    return render(request, 'artist_form.html', {'artist': artist})


def delete_view(request, artist_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        artist_service.delete_artist(session_id, artist_id)

    return redirect('artist_list')
