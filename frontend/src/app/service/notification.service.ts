import { Injectable, OnDestroy } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export type NotificationLevel = 'error' | 'warning' | 'success' | 'info';

export interface AppNotification {
  readonly id: number;
  readonly level: NotificationLevel;
  readonly message: string;
}

const AUTO_DISMISS_MS: Record<NotificationLevel, number> = {
  error: 10000,
  warning: 8000,
  success: 4000,
  info: 5000,
};

/**
 * In-app replacement for the global `alert()`.
 *
 * `alert()` blocks the UI thread, cannot be styled or tested, and stacks up one
 * modal per failed request when several calls fail at once.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService implements OnDestroy {
  private readonly subject = new BehaviorSubject<AppNotification[]>([]);
  private readonly timers = new Map<number, ReturnType<typeof setTimeout>>();
  private nextId = 1;

  readonly notifications$: Observable<AppNotification[]> = this.subject.asObservable();

  error(message: string): void {
    this.push('error', message);
  }

  warning(message: string): void {
    this.push('warning', message);
  }

  success(message: string): void {
    this.push('success', message);
  }

  info(message: string): void {
    this.push('info', message);
  }

  push(level: NotificationLevel, message: string): void {
    const text = (message ?? '').trim();
    if (!text) {
      return;
    }

    // Parallel requests routinely fail with the same message. Showing it once
    // and refreshing its timer keeps the stack readable.
    const existing = this.subject.value.find(
      (notification) => notification.level === level && notification.message === text
    );
    if (existing) {
      this.scheduleDismiss(existing);
      return;
    }

    const notification: AppNotification = { id: this.nextId++, level, message: text };
    this.subject.next([...this.subject.value, notification]);
    this.scheduleDismiss(notification);
  }

  dismiss(id: number): void {
    this.clearTimer(id);
    this.subject.next(
      this.subject.value.filter((notification) => notification.id !== id)
    );
  }

  clear(): void {
    this.subject.value.forEach((notification) => this.clearTimer(notification.id));
    this.subject.next([]);
  }

  ngOnDestroy(): void {
    this.clear();
  }

  private scheduleDismiss(notification: AppNotification): void {
    this.clearTimer(notification.id);
    this.timers.set(
      notification.id,
      setTimeout(() => this.dismiss(notification.id), AUTO_DISMISS_MS[notification.level])
    );
  }

  private clearTimer(id: number): void {
    const timer = this.timers.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
  }
}
