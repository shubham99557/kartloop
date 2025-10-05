from django.shortcuts import render, get_object_or_404, redirect
from core.models import Product
from core.forms import ProductForm
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def dashboard_home(request):
    return render(request, 'dashboard/dashboard_home.html')

@staff_member_required
def manage_products(request):
    products = Product.objects.all()
    return render(request, 'dashboard/manage_products.html', {'products': products})

@staff_member_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('dashboard:manage_products')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'dashboard/edit_product.html', {'form': form, 'product': product})
