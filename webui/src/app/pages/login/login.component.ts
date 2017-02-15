import {Component} from '@angular/core';
import {FormGroup, AbstractControl, FormBuilder, Validators} from '@angular/forms';
import { Router } from '@angular/router';

import { WebSocketService } from '../../services/index';

import { Subscription } from 'rxjs';

import 'style-loader!./login.scss';

@Component({
  selector: 'login',
  templateUrl: './login.html',
})
export class Login {

  public form:FormGroup;
  public username:AbstractControl;
  public password:AbstractControl;
  public submitted:boolean = false;
  public failed:boolean = false;

  private busy: Subscription;

  constructor(fb:FormBuilder, private _ws: WebSocketService, private _router: Router) {
    this._ws = _ws;
    this.form = fb.group({
      'username': ['', Validators.compose([Validators.required, Validators.minLength(4)])],
      'password': ['', Validators.compose([Validators.required])]
    });

    this.username = this.form.controls['username'];
    this.password = this.form.controls['password'];
  }

  ngOnInit() {
    if(this._ws.username && this._ws.password && this._ws.redirectUrl) {
      this.busy = this._ws.login(this._ws.username, this._ws.password).subscribe((result) => {
        this.loginCallback(result);
      });
    }
  }

  public onSubmit(values:Object):void {
    this.submitted = true;
    this.failed = false;
    if (this.form.valid) {
      this.busy = this._ws.login(this.username.value, this.password.value).subscribe((result) => {
        this.loginCallback(result);
      });
    }
  }

  loginCallback(result) {
    if(result === true) {
      this.successLogin();
    } else {
      this.errorLogin();
    }
    this.submitted = false;
  }

  successLogin() {
    if(this._ws.redirectUrl) {
      this._router.navigateByUrl(this._ws.redirectUrl);
      this._ws.redirectUrl = '';
    } else {
      this._router.navigate(['/pages', 'dashboard']);
    }
  }

  errorLogin() {
    this.failed = true;
  }


}
