# payment/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from .forms import TariffChoiceForm
from .models import Tariff, UserSubscription, Payment  # Импортируем Payment
from users.models import DiscordUser  # Импортируем DiscordUser, если еще не

def payment_page_view(request):
    if request.method == 'POST':
        form = TariffChoiceForm(request.POST)
        if form.is_valid():
            tariff = form.cleaned_data['tariff']
            request.session['selected_tariff_id'] = tariff.id
            return redirect(reverse('create_checkout_session'))  # Создадим этот URL позже
    else:
        form = TariffChoiceForm()
        tariffs = Tariff.objects.filter(is_active=True)
        context = {
            'form': form,
            'tariffs': tariffs,
        }
        return render(request, 'payment/payment_page.html', context)

def create_checkout_session(request):
    tariff_id = request.session.get('selected_tariff_id')
    if not tariff_id:
        return redirect(reverse('payment_page'))

    try:
        tariff = Tariff.objects.get(id=tariff_id)
        # --- Здесь будет логика создания платежной сессии с платежной системой ---
        # Пока просто эмулируем успешное создание и перенаправляем
        print(f"Эмулируем создание платежной сессии для тарифа: {tariff.name} ({tariff.price} USD)")
        return redirect(reverse('payment_success'))
    except Tariff.DoesNotExist:
        return redirect(reverse('payment_error'))
    except Exception as e:
        print(f"Ошибка при создании платежной сессии (эмуляция): {e}")
        return redirect(reverse('payment_error'))

def payment_success_view(request):
    tariff_id = request.session.get('selected_tariff_id')
    discord_user = request.user.discorduser if request.user.is_authenticated else None

    if tariff_id and discord_user:
        try:
            tariff = Tariff.objects.get(id=tariff_id)
            end_date = timezone.now() + timezone.timedelta(days=tariff.duration)
            subscription = UserSubscription.objects.create(user=discord_user, tariff=tariff, end_date=end_date)

            # Создаем запись о платеже и теперь сохраняем сумму
            Payment.objects.create(
                discord_user=discord_user,
                amount=tariff.price,  # <--- Используем цену тарифа
                payment_method='эмуляция',
                status='Успешно'
            )

            del request.session['selected_tariff_id']
            return render(request, 'payment/payment_success.html')
        except Tariff.DoesNotExist:
            return redirect(reverse('payment_error'))
    else:
        return redirect(reverse('payment_error'))

def payment_cancel_view(request):
    return render(request, 'payment/payment_cancel.html')

def payment_error_view(request):
    return render(request, 'payment/payment_error.html')
