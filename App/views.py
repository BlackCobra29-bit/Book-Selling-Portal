from django.shortcuts import render

# Create your views here.
def Index(request):

    return render(request, 'index.html')

def Dashboard(request):

    return render(request, 'admin/dashboard.html')