import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { EntityListComponent } from './entity-list/index';

@Component({
  selector: 'app-entity',
  templateUrl: 'entity.component.html',
  styleUrls: ['entity.component.css']
})
export class EntityComponent implements OnInit {

  constructor(private router: Router) {}

  ngOnInit() {
  }

}
