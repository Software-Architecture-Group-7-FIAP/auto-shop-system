import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-head-navigation',
  templateUrl: './head-navigation.component.html',
  styleUrls: ['./head-navigation.component.css'],
})
export class HeadNavigationComponent {
  @Input() titleText = '';
  @Input() toCreatingMode!: () => void;
  @Input() showAdd = true;
}
