# users/forms.py
from django import forms

class MinecraftInfoForm(forms.Form):
    platform_choices = [
        ('java', 'Java Edition'),
        ('bedrock', 'Bedrock Edition'),
    ]
    platform = forms.ChoiceField(choices=platform_choices, widget=forms.RadioSelect(), label='Выберите версию Minecraft')
    java_nickname = forms.CharField(max_length=16, required=False, label='Никнейм Java')
    bedrock_nickname = forms.CharField(max_length=32, required=False, label='Xbox никнейм (Bedrock)')

    def clean(self):
        cleaned_data = super().clean()
        platform = cleaned_data.get('platform')
        java_nickname = cleaned_data.get('java_nickname')
        bedrock_nickname = cleaned_data.get('bedrock_nickname')

        if platform == 'java' and not java_nickname:
            raise forms.ValidationError('Пожалуйста, введите ваш никнейм Java.')
        elif platform == 'bedrock' and not bedrock_nickname:
            raise forms.ValidationError('Пожалуйста, введите ваш Xbox никнейм.')
        elif platform == 'java' and bedrock_nickname:
            cleaned_data['bedrock_nickname'] = None
        elif platform == 'bedrock' and java_nickname:
            cleaned_data['java_nickname'] = None

        return cleaned_data