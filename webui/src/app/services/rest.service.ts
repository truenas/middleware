import { Injectable } from '@angular/core';
import { Http, Headers, Request, RequestMethod, RequestOptions, Response } from '@angular/http';
import 'rxjs/Rx';
import 'rxjs/add/observable/throw';
import 'rxjs/add/operator/map';
import 'rxjs/add/operator/toPromise';
import { Observable } from 'rxjs/Observable';

import { WebSocketService } from './ws.service';

@Injectable()
export class RestService {

  name: string;
  private baseUrl: string = "/api/v1.0/";
  public openapi: Observable<Object>;

  constructor(private http: Http, private ws: WebSocketService) {
    let self = this;
    this.http = http;
    this.openapi = Observable.create(function(observer) {
      self.get('swagger.json', {}).subscribe((res) => {
        observer.next(res.data);
      });
    });
  }

  handleResponse(res: Response) {
    let range = res.headers.get("CONTENT-RANGE");
    let total = null;
    let data = null;
    if(range) {
      total = range.split('/');
      total = new Number(total[total.length - 1]);
    }
    if(res.status != 204) {
      data = res.json();
    }
    return {
      data: data,
      code: res.status,
      total: total,
    };
  }

  handleError(error: any) {
    return Observable.throw({
      error: error.json(),
      code: error.status,
    });
  }

  request(method: RequestMethod, path: string, options: Object) {
    let headers = new Headers({
      'Content-Type': 'application/json',
      'Authorization': 'Basic ' + btoa(this.ws.username + ':' + this.ws.password)
    });
    let requestOptions:Object = Object.assign({
      method: method,
      url: this.baseUrl + path,
      headers: headers
    }, options);
    return this.http.request(new Request(new RequestOptions(requestOptions)))
      .map(this.handleResponse).catch(this.handleError);
  }

  buildOptions(options) {
    let result:Object = new Object();
    let search:Array<String> = [];
    for(let i in options) {
       if(i == 'offset') {
         search.push("offset(" + options[i] + ")=");
       } else if(i == 'sort') {
         search.push("sort(" + options[i] + ")=");
       } else {
         search.push(i + "=" + options[i]);
       }
    }
    result['search'] = search.join("&");
    return result;
  }

  get(path: string, options: Object) {
    return this.request(RequestMethod.Get, path, this.buildOptions(options));
  }

  post(path: string, options: Object) {
    return this.request(RequestMethod.Post, path, options);
  }

  put(path: string, options: Object) {
    return this.request(RequestMethod.Put, path, options);
  }

  delete(path: string, options: Object) {
    return this.request(RequestMethod.Delete, path, options);
  }

}
