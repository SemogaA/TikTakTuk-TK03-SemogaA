from django.shortcuts import render

def checkout(request):
    event = {
        'event_title':    'Konser Melodi Senja',
        'event_datetime': '2024-06-15 18:00',
        'venue_name':     'Jakarta Convention Center',
        'artists':        [{'name': 'Raisa'}, {'name': 'Hindia'}],
    }
    categories = [
        {'category_id': '1', 'category_name': 'WVIP',       'quota': 50,  'price': 1500000},
        {'category_id': '2', 'category_name': 'VIP',        'quota': 150, 'price': 750000},
        {'category_id': '3', 'category_name': 'Category 1', 'quota': 300, 'price': 450000},
        {'category_id': '4', 'category_name': 'Category 2', 'quota': 500, 'price': 250000},
    ]
    seats = [
        {'seat_id': f'{r}{n}', 'section': 'A', 'row_number': r, 'seat_number': n, 'is_taken': False}
        for r in ['A','B','C'] for n in range(1, 5)
    ]
    return render(request, 'checkout.html', {
        'event':       event,
        'categories':  categories,
        'seats':       seats,
        'is_reserved': True,
    })