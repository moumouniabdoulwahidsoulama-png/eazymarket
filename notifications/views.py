from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Notification

@login_required
def notification_list(request):
    """Liste des notifications de l'utilisateur"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Marquer toutes les notifications comme lues
    unread = notifications.filter(is_read=False)
    for notif in unread:
        notif.mark_as_read()
    
    context = {
        'notifications': notifications,
    }
    return render(request, 'notifications/list.html', context)

@login_required
def notification_count(request):
    """API pour le nombre de notifications non lues"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def notification_mark_read(request, notification_id):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('notification_list')

@login_required
def notification_delete(request, notification_id):
    """Supprimer une notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, "Notification supprimée")
    return redirect('notification_list')

@login_required
def notification_clear_all(request):
    """Supprimer toutes les notifications"""
    Notification.objects.filter(user=request.user).delete()
    messages.success(request, "Toutes les notifications ont été supprimées")
    return redirect('notification_list')