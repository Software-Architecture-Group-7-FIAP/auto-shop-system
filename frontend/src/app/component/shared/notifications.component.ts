import { Component } from '@angular/core';
import { Observable } from 'rxjs';

import { AppNotification, NotificationService } from '../../service/notification.service';

@Component({
  selector: 'app-notifications',
  templateUrl: './notifications.component.html',
  styleUrls: ['./notifications.component.css'],
})
export class NotificationsComponent {
  readonly notifications$: Observable<AppNotification[]>;

  constructor(private notificationService: NotificationService) {
    this.notifications$ = notificationService.notifications$;
  }

  dismiss(id: number): void {
    this.notificationService.dismiss(id);
  }

  trackById(_index: number, notification: AppNotification): number {
    return notification.id;
  }
}
