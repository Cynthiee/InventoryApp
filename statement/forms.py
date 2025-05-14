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
        fields = []
       

InventoryStatementItemFormSet = inlineformset_factory(
    InventoryStatement,
    InventoryStatementItem,
    form=InventoryStatementItemForm,
    extra=0,
    can_delete=False
)
