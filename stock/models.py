from django.db import models  
from django.contrib.auth.models import User  
from django.core.validators import MinValueValidator  
from django.db.models import Sum  
from django.db.models.signals import post_save  
from django.dispatch import receiver  

class Category(models.Model):  
    name = models.CharField(max_length=200, blank=False)  
    slug = models.SlugField(max_length=200, unique=True)  

    class Meta:  
        ordering = ['name']  
        indexes = [models.Index(fields=['name'])]  
        verbose_name = 'category'  
        verbose_name_plural = 'categories'  

    def __str__(self):  
        return self.name  


class Product(models.Model):  
    category = models.ForeignKey(Category, blank=False, related_name='products', on_delete=models.CASCADE)  
    name = models.CharField(max_length=200)  
    slug = models.SlugField(max_length=200)   
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])  
    bulk_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])  
    quantity = models.IntegerField(validators=[MinValueValidator(0)])  
    minimum_bulk_quantity = models.IntegerField(  
        default=12,  
        help_text="Minimum quantity required for bulk pricing."  
    )  
    restock_level = models.IntegerField(  
        validators=[MinValueValidator(0)],  
        default=0,  
        help_text="Minimum quantity before restock is needed."  
    )  
    needs_restock = models.BooleanField(default=False)  
    available = models.BooleanField(default=True)  
    created = models.DateTimeField(auto_now_add=True)  
    updated = models.DateTimeField(auto_now=True)  

    class Meta:  
        ordering = ['name']  
        indexes = [  
            models.Index(fields=['id', 'slug']),  
            models.Index(fields=['name']),  
            models.Index(fields=['-created']),  
        ]  

    def __str__(self):  
        return self.name  

    def save(self, *args, **kwargs):  
        # Update needs_restock status before saving  
        self.needs_restock = self.quantity <= self.restock_level  
        # Ensure bulk_price is less than or equal to regular_price  
        if self.bulk_price > self.regular_price:  
            raise ValueError("Bulk price cannot be greater than regular price.")  
        super().save(*args, **kwargs)  


class Sale(models.Model):  
    product = models.ForeignKey(Product, related_name='%(class)s_sales', on_delete=models.CASCADE)  
    quantity = models.IntegerField(validators=[MinValueValidator(1)])  
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  
    sale_date = models.DateTimeField(auto_now_add=True)  
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  
    created = models.DateTimeField(auto_now_add=True)  
    updated = models.DateTimeField(auto_now=True)  

    class Meta:  
        abstract = True  

    def __str__(self):  
        return f"{self.product.name} - {self.quantity} units"  


class RegularSale(Sale):  
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)  

    def save(self, *args, **kwargs):  
        self.total_amount = self.quantity * self.price_per_unit  
        super().save(*args, **kwargs)  


class BulkSale(Sale):  
    bulk_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)  

    def save(self, *args, **kwargs):  
        self.total_amount = self.quantity * self.bulk_price_per_unit  
        super().save(*args, **kwargs)  


class InventoryStatement(models.Model):  
    date = models.DateField(auto_now_add=True)  
    total_income = models.DecimalField(max_digits=15, decimal_places=2, editable=False)  
    total_products_sold = models.IntegerField(editable=False)  
    total_products_in_stock = models.IntegerField(editable=False)  

    @property  
    def calculate_total_sales(self):  
        regular_total = RegularSale.objects.filter(sale_date__date=self.date).aggregate(  
            total=Sum('total_amount'))['total'] or 0  
        bulk_total = BulkSale.objects.filter(sale_date__date=self.date).aggregate(  
            total=Sum('total_amount'))['total'] or 0  
        return regular_total + bulk_total  

    @property  
    def calculate_total_products_sold(self):  
        regular_quantity = RegularSale.objects.filter(sale_date__date=self.date).aggregate(  
            total=Sum('quantity'))['total'] or 0  
        bulk_quantity = BulkSale.objects.filter(sale_date__date=self.date).aggregate(  
            total=Sum('quantity'))['total'] or 0  
        return regular_quantity + bulk_quantity  

    def save(self, *args, **kwargs):  
        self.total_income = self.calculate_total_sales  
        self.total_products_sold = self.calculate_total_products_sold  
        self.total_products_in_stock = Product.objects.aggregate(Sum('quantity'))['quantity__sum'] or 0  
        super().save(*args, **kwargs)  

    class Meta:  
        ordering = ['date']  
        indexes = [  
            models.Index(fields=['id', 'date']),  
            models.Index(fields=['date']),  
        ]  

    def __str__(self):  
        return str(self.date)