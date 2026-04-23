from django.shortcuts import render, redirect
from django.http import HttpResponse
from tiktaktuk.services import user as user_service


def home_view(request):
    """
    halaman landing page untuk guest.
    kalau ternyata udah punya cookie session, arahin langsung ke dashboard.
    """
    session_id = request.COOKIES.get('session_id')
    if session_id and user_service.validate_session(session_id):
        return redirect('dashboard')

    return render(request, 'home.html')


def login_view(request):
    """
    handle form get dan post untuk login.
    """
    if request.COOKIES.get('session_id') and user_service.validate_session(request.COOKIES.get('session_id')):
        return redirect('dashboard')

    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        password = request.POST.get('password')

        result = user_service.login_user(identifier, password)

        if result:
            response = redirect('dashboard')
            response.set_cookie(
                'session_id', result['session_id'], max_age=86400)
            return response
        else:
            return render(request, 'login.html', {'error': 'email/username atau password salah!'})

    return render(request, 'login.html')


def register_view(request):
    """
    handle registrasi pengguna baru.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role_name = request.POST.get('role_name')

        profile_data = {}
        if role_name == 'customer':
            profile_data['full_name'] = request.POST.get('full_name')
            profile_data['phone_number'] = request.POST.get('phone_number')
        elif role_name == 'organizer':
            profile_data['organizer_name'] = request.POST.get('organizer_name')

        user_id = user_service.register_user_atomic(
            username, email, password, role_name, profile_data)

        if user_id:
            return redirect('login')
        else:
            return render(request, 'register.html', {'error': 'registrasi gagal. username/email mungkin sudah terpakai.'})

    return render(request, 'register.html')


def logout_view(request):
    """
    handle logout, kill session di db dan hapus cookie di browser.
    """
    session_id = request.COOKIES.get('session_id')
    if session_id:
        user_service.logout_user(session_id)

    response = redirect('login')
    response.delete_cookie('session_id')
    return response


def dashboard_view(request):
    """
    nampilin data dashboard berdasarkan role.
    """
    session_id = request.COOKIES.get('session_id')

    if not session_id:
        return redirect('login')

    dashboard_data = user_service.get_dashboard_data(session_id)

    if not dashboard_data:
        response = redirect('login')
        response.delete_cookie('session_id')
        return response

    context = {
        'dashboard': dashboard_data,
        'roles': dashboard_data['roles'],
        'username': dashboard_data['username']
    }

    return render(request, 'dashboard.html', context)
