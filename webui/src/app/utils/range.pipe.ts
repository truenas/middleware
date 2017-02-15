import { Pipe, PipeTransform } from '@angular/core';

@Pipe({name: 'range'})
export class RangePipe implements PipeTransform {
  transform(value: number): number[] {
    return Array<number>(value).fill(0).map((x,i)=>i);
  }
}
