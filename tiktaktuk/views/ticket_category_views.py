from django.shortcuts import render, redirect
from tiktaktuk.services import ticket_category as category_service
from tiktaktuk.services import user as user_service

def list_view(request):
    session_id = request.COOKIES.get('session_id')
    
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id) if session_id else {}
    role = profile_data.get('role') if profile_data else 'guest'
    
    categories = category_service.get_all_ticket_categories()
    
    return render(request, 'ticket_category/category_list.html', {
        'categories': categories, 
        'role': role,
        'total_categories': len(categories),
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def create_view(request):
    session_id = request.COOKIES.get('session_id')
    
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id) if session_id else {}
    role = profile_data.get('role')
    
    if role not in ['administrator', 'organizer']:
        return redirect('category_list')

    if request.method == 'POST':
        name = request.POST.get('category_name')
        price = request.POST.get('price')
        quota = request.POST.get('quota')
        event_id = request.POST.get('tevent_id')

        result = category_service.create_ticket_category(session_id, name, price, quota, event_id)
        if result:
            return redirect('category_list')
        else:
            return render(request, 'ticket_category/category_form.html', {
                'error': 'Gagal menambah kategori. Pastikan Event ID valid dan kuota tidak melebihi kapasitas venue.',
                'role': role,
                'dashboard': profile_data, 
                'username': profile_data.get('username') 
            })

    return render(request, 'ticket_category/category_form.html', {
        'role': role,
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def update_view(request, category_id):
    session_id = request.COOKIES.get('session_id')
    
    # Tarik data profil
    profile_data = user_service.get_profile_data(session_id) if session_id else {}
    role = profile_data.get('role')
    
    if role not in ['administrator', 'organizer']:
        return redirect('category_list')

    category = category_service.get_ticket_category_by_id(category_id)

    if request.method == 'POST':
        name = request.POST.get('category_name')
        price = request.POST.get('price')
        quota = request.POST.get('quota')

        success = category_service.update_ticket_category(session_id, category_id, name, price, quota)
        if success:
            return redirect('category_list')
        else:
            return render(request, 'ticket_category/category_form.html', {
                'category': category,
                'error': 'Gagal memperbarui kategori. Periksa kembali batasan kuota.',
                'role': role,
                'dashboard': profile_data, 
                'username': profile_data.get('username') 
            })

    return render(request, 'ticket_category/category_form.html', {
        'category': category, 
        'role': role,
        'dashboard': profile_data, 
        'username': profile_data.get('username') 
    })

def delete_view(request, category_id):
    session_id = request.COOKIES.get('session_id')
    if request.method == 'POST':
        category_service.delete_ticket_category(session_id, category_id)
    return redirect('category_list')