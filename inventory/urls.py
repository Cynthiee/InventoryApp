from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home/', include('products.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
    path('sales/', include('sales.urls')),
    path('statement/', include('statement.urls')),

]