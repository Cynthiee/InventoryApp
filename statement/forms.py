from django import forms
from django.forms import inlineformset_factory
from .models import InventoryStatement, InventoryStatementItem

class InventoryStatementForm(forms.ModelForm):
    class Meta:
        model = InventoryStatement
        fields = ['company_name', 'prepared_by', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class InventoryStatementItemForm(forms.ModelForm):
    class Meta:
        model = InventoryStatementItem
        fields = ['received_stock']
        widgets = {
            'received_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        }

    def clean_received_stock(self):
        received_stock = self.cleaned_data.get('received_stock')
        if received_stock < 0:
            raise forms.ValidationError("Received stock cannot be negative")
        return received_stock


InventoryStatementItemFormSet = inlineformset_factory(
    InventoryStatement,
    InventoryStatementItem,
    form=InventoryStatementItemForm,
    extra=0,
    can_delete=False
)
