from django.shortcuts import render, redirect
from tiktaktuk.services import artist as artist_service
from tiktaktuk.services import user as user_service 

def list_view(request):
    session_id = request.COOKIES.get('session_id')
    
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id) if session_id else {}
    role = profile_data.get('role')
    
    artists = artist_service.get_all_artists()
    return render(request, 'artist/artist_list.html', {
        'artists': artists, 
        'role': role,
        'total_artists': len(artists),
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def create_view(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')
        
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        genre = request.POST.get('genre')

        artist_id = artist_service.create_artist(session_id, name, genre)
        if artist_id:
            return redirect('artist_list')
        else:
            return render(request, 'artist/artist_form.html', {
                'error': 'gagal membuat artis.',
                'role': profile_data.get('role'), 
                'dashboard': profile_data, 
                'username': profile_data.get('username') 
            })

    return render(request, 'artist/artist_form.html', {
        'role': profile_data.get('role'), 
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def update_view(request, artist_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')
        
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        genre = request.POST.get('genre')

        success = artist_service.update_artist(
            session_id, artist_id, name, genre)
        if success:
            return redirect('artist_list')
        else:
            artist = artist_service.get_artist_by_id(artist_id)
            return render(request, 'artist/artist_form.html', {
                'artist': artist, 
                'error': 'gagal update artis.',
                'role': profile_data.get('role'), 
                'dashboard': profile_data, 
                'username': profile_data.get('username') 
            })

    artist = artist_service.get_artist_by_id(artist_id)
    return render(request, 'artist/artist_form.html', {
        'artist': artist,
        'role': profile_data.get('role'), 
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def delete_view(request, artist_id):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'POST':
        artist_service.delete_artist(session_id, artist_id)

    return redirect('artist_list')