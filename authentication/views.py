from django.shortcuts import render

def register_select_role(request):
    return render(request, 'register.html')

def register_customer(request):
    return render(request, 'register.html', {'role': 'customer'})

def register_organizer(request):
    return render(request, 'register.html', {'role': 'organizer'})

def register_admin(request):
    return render(request, 'register.html', {'role': 'admin'})