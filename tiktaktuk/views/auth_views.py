from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from tiktaktuk.services import user as user_service
import re


def home_view(request):
    """
    redirect ke login page.
    kalau ternyata udah punya cookie session, arahin langsung ke dashboard.
    """
    session_id = request.COOKIES.get('session_id')
    if session_id and user_service.validate_session(session_id):
        return redirect('dashboard')

    return render(request, 'auth/login.html')


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
            return render(request, 'auth/login.html', {'error': 'email / username atau password salah!'})

    return render(request, 'auth/login.html')


def register_view(request):
    """
    handle registrasi pengguna baru.
    """
    if request.method == 'POST':
        # check apakah ini request dari Fetch API (AJAX)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role_name = request.POST.get('role_name')

        if password != confirm_password:
            msg = 'Password dan Konfirmasi Password tidak cocok!'
            if is_ajax:
                return JsonResponse({'error': msg}, status=400)
            return render(request, 'auth/register.html', {'error': msg})

        if len(password) < 6:
            msg = 'Password minimal harus 6 karakter!'
            if is_ajax:
                return JsonResponse({'error': msg}, status=400)
            return render(request, 'auth/register.html', {'error': msg})

        if not re.match(r'^[a-zA-Z0-9]+$', username):
            msg = 'Username hanya boleh berisi huruf dan angka (tanpa spasi)!'
            if is_ajax:
                return JsonResponse({'error': msg}, status=400)
            return render(request, 'auth/register.html', {'error': msg})

        phone_number = request.POST.get('phone_number')

        if role_name == 'customer' and phone_number:
            if not re.match(r'^\+?[0-9]+$', phone_number):
                msg = 'Nomor telepon tidak valid, hanya boleh angka!'
                if is_ajax:
                    return JsonResponse({'error': msg}, status=400)
                return render(request, 'auth/register.html', {'error': msg})

        profile_data = {}
        if role_name == 'customer':
            profile_data['full_name'] = request.POST.get('full_name')
            profile_data['phone_number'] = phone_number
        elif role_name == 'organizer':
            profile_data['organizer_name'] = request.POST.get('organizer_name')

        user_id = user_service.register_user_atomic(
            username, email, password, role_name, profile_data)

        if user_id:
            if is_ajax:
                return JsonResponse({'success': True, 'redirect_url': '/login/'})
            return redirect('login')
        else:
            msg = 'Registrasi gagal. Username / email sudah digunakan.'
            if is_ajax:
                return JsonResponse({'error': msg}, status=400)
            return render(request, 'auth/register.html', {'error': msg})

    return render(request, 'auth/register.html')


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
        'role': dashboard_data['role'],
        'username': dashboard_data['username']
    }

    return render(request, 'auth/dashboard.html', context)


def profile_view(request):
    session_id = request.COOKIES.get('session_id')
    if not session_id:
        return redirect('login')

    if request.method == 'GET':
        profile_data = user_service.get_profile_data(session_id)
        if not profile_data:
            return redirect('logout')

        context = {
            'profile': profile_data,
            'dashboard': {'role': profile_data['role']},
            'username': profile_data['username']
        }
        return render(request, 'auth/profile.html', context)

    elif request.method == 'POST':
        is_success = False
        message = ""

        # buat update informasi profil
        if 'update_info' in request.POST:
            update_data = {
                'email': request.POST.get('email'),
                'full_name': request.POST.get('full_name'),
                'phone_number': request.POST.get('phone_number'),
                'organizer_name': request.POST.get('organizer_name'),
                'contact_email': request.POST.get('contact_email'),
            }
            is_success, message = user_service.update_profile_info(
                session_id, update_data)

        # buat update password
        elif 'update_password' in request.POST:
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            # validasi Konfirmasi Password
            if new_password != confirm_password:
                is_success, message = False, "Konfirmasi password tidak cocok!"
            elif len(new_password) < 6:
                is_success, message = False, "Password baru minimal harus 6 karakter."
            else:
                is_success, message = user_service.change_user_password(
                    session_id, old_password, new_password)

        # tarik ulang data terbaru untuk di-render kembali ke form
        profile_data = user_service.get_profile_data(session_id)

        context = {
            'profile': profile_data,
            'dashboard': {'role': profile_data['role']},
            'username': profile_data['username'],
            'message': message,
            'success': is_success
        }
        return render(request, 'auth/profile.html', context)
