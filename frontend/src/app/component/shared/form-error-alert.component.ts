import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-form-error-alert',
  templateUrl: './form-error-alert.component.html',
  styleUrls: ['./form-error-alert.component.css'],
})
export class FormErrorAlertComponent {
  @Input() title = 'Verifique os dados informados';
  @Input() message = '';
}
