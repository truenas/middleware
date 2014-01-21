require([
    "dojo/_base/fx",
    "dojo/dom",
    "dojo/dom-construct",
    "dojo/dom-style",
    "dojo/fx",
    "dojo/html",
    "dojo/query",
    "dojo/request/xhr",
    "freeadmin/reporting/registry"
    ], function(
    basefx,
    dom,
    construct,
    style,
    fx,
    html,
    query,
    xhr,
    rRegistry) {
    /*
    Chart helper functions. These functions are intendent to help process and name charts within the reporting section
    */

    rregistry = rRegistry({});

    chart_update = function(url, container, tg, range, t_date, t_type) {
        var MyTypes = tg.split(",");
        MyTypes.forEach(function(value, index) {
            series_chart(url+value+'/octets/' + range +'/'+ t_date +'/', container+index, t_type +' '+ value.charAt(0).toUpperCase() + value.slice(1) + ' ' + gettext('Utilization'));
        });
    };

    chart_update_cpu = function(url, container, tg, range, t_date, t_type) {
        var MyTypes = tg.split(",");
        MyTypes.forEach(function(value, index) {
            series_chart(url+value+'/' + range +'/'+ t_date +'/0/', container+index, t_type +' '+ value.replace('_', ' ').toUpperCase() +' Utilization');
        });

    };

    chart_update_cpu_agg = function(url, container, tg, range, t_date, t_type) {
        var MyTypes = tg.split(",");
        MyTypes.forEach(function(value, index) {
            console.log(url, 'aggregate/' + range +'/'+ t_date, "--", value);
            series_chart(url + 'aggregate/' + range +'/'+ t_date + '/', container+value, 'Composite CPU Utilization');
            console.log("ok?")
        });

    };

    chart_update_mem = function(url, container, range, t_date, attrs) {
        series_chart(url + range +'/'+ t_date +'/', container ,'System Memory Utilization', attrs);
    };

    series_sub = function(url, container, tg, name, sub_types) {
        var MyTypes = sub_types.split(",");
        MyTypes.forEach(function(value, index) {
            series_chart(url+value+'/', container+value, name + ' ' +value);
        });
    };

    chart_switch = function(switch_in, switch_out) {
        var _in, _out;
        _in = dojo.query(switch_in)[0];
        _out = dojo.query(switch_out)[0];
        fx.chain([
            basefx.fadeOut({
                node: _out,
                onEnd: function() { style.set(_out, "display", "none"); }
            }),
            basefx.fadeIn({
                node: _in,
                onEnd: function() { style.set(_in, "display", "block"); }
            })
        ]).play();
    };


    /*
    Chart functions to create charts
    */

    z_tank = function(volid, url, url_info) {
        z_info(volid, url_info);
        tank_pie(url, 'tankPie' + volid);
    };

    z_info = function(volid, url_info) {
        xhr.get(url_info, {
            handleAs: 'json'
        }).then(function(data) {

            var div = dom.byId("tank" + volid);
            construct.empty("tank_body" + volid);

            for(var k in data) {
                var v = data[k];
                if(k=='name'){
                    var pt_name = dojo.query(".partition_name", div)[0];
                    pt_name.innerHTML = v;
                } else {
                    construct.create("tr", { innerHTML: '<td> '+k+' </td> <td> '+v+' </td>' }, "tank_body" + volid);
                }
            }
            style.set(div, "display", "block");

      });

    };

    rt_network = function(url, container){
        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.Chart({
                chart: {
                    renderTo: container,
                    type: 'gauge',
                    plotBorderWidth: 1,
                    plotBackgroundColor: {
                        linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                        stops: [
                            [0, '#FFF4C6'],
                            [0.3, '#FFFFFF'],
                            [1, '#FFF4C6']
                        ]
                    },
                    plotBackgroundImage: null,
                    height: 200
                },
                credits: {
                    enabled: false
                },
                title: {
                    text: 'Network meter'
                },
                pane: [{
                    startAngle: -45,
                    endAngle: 45,
                    background: null,
                    center: ['25%', '145%'],
                    size: 300
                }, {
                    startAngle: -45,
                    endAngle: 45,
                    background: null,
                    center: ['75%', '145%'],
                    size: 300
                }],
                yAxis: [{
                    min: 0,
                    max: 1000000000,
                    minorTickPosition: 'outside',
                    tickPosition: 'outside',
                    labels: {
                        rotation: 'auto',
                        distance: 20
                    },
                    plotBands: [{
                        from: 0,
                        to: 6,
                        color: '#C02316',
                        innerRadius: '100%',
                        outerRadius: '105%'
                    }],
                    pane: 0,
                    title: {
                        text: 'Network<br/><span style="font-size:8px">Write</span>',
                        y: -40
                    }
                    }, {
                    min: 0,
                    max: 1000000000,
                    minorTickPosition: 'outside',
                    tickPosition: 'outside',
                    labels: {
                        rotation: 'auto',
                        distance: 20
                    },
                    plotBands: [{
                        from: 0,
                        to: 6,
                        color: '#C02316',
                        innerRadius: '100%',
                        outerRadius: '105%'
                    }],
                    pane: 1,
                    title: {
                        text: 'Network<br/><span style="font-size:8px">Read</span>',
                        y: -40
                    }
                }],
                plotOptions: {
                    gauge: {
                        dataLabels: {
                            enabled: false
                        },
                        dial: {
                            radius: '100%'
                        }
                    }
                },
                series: [{
                    data: [data['tx']],
                    yAxis: 0
                }, {
                    data: [data['rx']],
                    yAxis: 1
                }]
            },
            // Let the network flow
            function(chart) {
                setInterval(function() {
                    if(typeof chart.series == 'undefined') return;
                    var left = chart.series[0].points[0],
                        right = chart.series[1].points[0];
                    xhr.get(url, {
                        handleAs: 'json'
                    }).then(function(data) {
                        if(data['tx'] > 1000000000) data['tx'] = 1000000000;
                        if(data['rx'] > 1000000000) data['rx'] = 1000000000;
                        left.update(data['tx'], false);
                        right.update(data['rx'], false);
                        chart.redraw();
                    });
                }, 5000);
            });
            rregistry.add(chart, url);
        });
    };

    rt_df = function(title, url, container) {
        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.Chart({
                chart: {
                    renderTo: container,
                    type: 'gauge',
                    plotBorderWidth: 1,
                    plotBackgroundColor: {
                        linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                        stops: [
                            [0, '#FFF4C6'],
                            [0.3, '#FFFFFF'],
                            [1, '#FFF4C6']
                        ]
                    },
                    plotBackgroundImage: null,
                    height: 200
                },
                credits: {
                    enabled: false
                },
                title: {
                    text: title
                },
                pane: [{
                    startAngle: -45,
                    endAngle: 45,
                    background: null,
                    center: ['50%', '145%'],
                    size: 300
                }],
                yAxis: [{
                    min: 0,
                    max: 100,
                    minorTickPosition: 'outside',
                    tickPosition: 'outside',
                    tickColor: '#fff',
                    labels: {
                        rotation: 'auto',
                        distance: 20
                    },
                    plotBands: [{
                        from: 65,
                        to: 80,
                        color: '#ffff00',
                        innerRadius: '100%',
                        outerRadius: '105%'
                    },{
                        from: 80,
                        to: 100,
                        color: '#C02316',
                        innerRadius: '100%',
                        outerRadius: '105%'
                    }],
                    pane: 0,
                    title: {
                        text: 'Partition <br/><span style="font-size:8px">Utilization</span>',
                        y: -40
                    }
                }],
                plotOptions: {
                    gauge: {
                        dataLabels: {
                            enabled: false
                        },
                        dial: {
                            radius: '100%'
                        }
                    }
                },
                plotBands: [],
                series: [{
                    data: [data],
                    yAxis: 0
                }]
            },
            // Let the partitions float
            function(chart) {
                setInterval(function() {
                    if(typeof chart.series == 'undefined') return;
                    var left = chart.series[0].points[0];
                    xhr.get(url, {
                        handleAs: 'json'
                    }).then(function(data) {
                        left.update(data, false);
                        chart.redraw();
                    });
                }, 10000);
            });
            rregistry.add(chart, url);
        });
    };

    rt_cpu = function(url, container){
        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.Chart({
                chart: {
                    renderTo: container,
                    type: 'gauge',
                    plotBackgroundColor: null,
                    plotBackgroundImage: null,
                    plotBorderWidth: 0,
                    plotShadow: false
                },
                title: '',
                credits: {
                    enabled: false
                },
                pane: {
                    startAngle: -150,
                    endAngle: 150,
                    background: [{
                        backgroundColor: {
                        linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                        stops: [
                            [0, '#FFF'],
                            [1, '#333']
                        ]
                        },
                        borderWidth: 0,
                        outerRadius: '109%'
                    }, {
                        backgroundColor: {
                        linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
                        stops: [
                            [0, '#333'],
                            [1, '#FFF']
                        ]
                        },
                        borderWidth: 1,
                        outerRadius: '107%'
                    }, {
                        // default background
                    }, {
                        backgroundColor: '#DDD',
                        borderWidth: 0,
                        outerRadius: '105%',
                        innerRadius: '103%'
                    }]
                },
                // the value axis
                yAxis: {
                    min: 0,
                    max: 100,
                    minorTickInterval: 'auto',
                    minorTickWidth: 1,
                    minorTickLength: 10,
                    minorTickPosition: 'inside',
                    minorTickColor: '#666',
                    tickPixelInterval: 30,
                    tickWidth: 2,
                    tickPosition: 'inside',
                    tickLength: 10,
                    tickColor: '#666',
                    labels: {
                        step: 2,
                        rotation: 'auto'
                    },
                    title: {
                        text: 'CPU <br/>Utilization'
                    },
                    plotBands: [{
                        from: 0,
                        to: 70,
                        color: '#55BF3B' // green
                    }, {
                        from: 70,
                        to: 80,
                        color: '#DDDF0D' // yellow
                    }, {
                        from: 80,
                        to: 100,
                        color: '#DF5353' // red
                    }]
                },
                series: [{
                    name: 'CPU',
                    data: [data],
                    tooltip: {
                        valueSuffix: '%'
                    }
                }]
            },
            // Add some life
            function (chart) {
                setInterval(function() {
                    if(typeof chart.series == 'undefined') return;
                    var left = chart.series[0].points[0];
                    xhr.get(url, {
                        handleAs: 'json'
                    }).then(function(data) {
                        left.update(data, false);
                        chart.redraw();
                    });
                }, 10000);
            });
            rregistry.add(chart, url);
        });
    };

    series_chart = function(url, container, title, attrs) {
        if(!attrs) {
          attrs = {};
        }

        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.StockChart({
                chart: {
                    renderTo: container
                },
                rangeSelector: {
                    enabled: false
                },
                credits: {
                     enabled: false
                },
                title: {
                    text: title
                },
                plotBands: [],
                series: data,
                exporting: {
                    enabled: false
                },
                tooltip: attrs['tooltip']
            });
        });
    };

    storage_pie = function(url, container) {
        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.Chart({
                chart: {
                    renderTo: container,
                    plotBackgroundColor: null,
                    plotBorderWidth: null,
                    plotShadow: false
                },
                title: {
                    text: data.name
                },
                credits: {
                    enabled: false
                    },
                tooltip: {
                    formatter: function() {
                        return '<b>'+ this.point.name +'</b>: '+ this.percentage.toFixed(2) +' %' + '<br><b>Space Used</b>: '+pretty_number(this.y, {'short': true});
                    }
                },
                plotOptions: {
                    pie: {
                        allowPointSelect: true,
                        cursor: 'pointer',
                        dataLabels: {
                            enabled: true,
                            color: '#ffffff',
                            connectorColor: '#000000',
                            formatter: function() {
                                return '<b>'+ this.point.name +'</b>: '+ this.percentage.toFixed(2) +' %';
                            }
                        }
                    }
                },
                series: [data]
            },
            // Let the partitions float
            function(chart) {
                setInterval(function() {
                    if(typeof chart.series == 'undefined') return;
                    xhr.get(url, {
                        handleAs: 'json'
                    }).then(function(data) {
                        chart.series[0].setData(data.data, true);
                    });
                }, 10000);
            });
            rregistry.add(chart, url);
        });
    };

    tank_pie = function(url, container) {
        style.set(container, "display", "block");
        xhr.get(url, {
            handleAs: 'json'
        }).then(function(data) {
            var chart = new Highcharts.Chart({
                chart: {
                    renderTo: container,
                    plotBackgroundColor: null,
                    plotBorderWidth: null,
                    plotShadow: false
                },
                title: {
                    text: data.title
                },
                credits: {
                    enabled: false
                },
                tooltip: {
                    formatter: function() {
                        return '<b>'+ this.point.name +'</b>: '+ this.percentage.toFixed(2) +' %' + '<br><b>Space Used</b>: '+pretty_number(this.y, {'short': true});
                    }
                },
                plotOptions: {
                    pie: {
                        allowPointSelect: true,
                        cursor: 'pointer',
                        dataLabels: {
                            enabled: true,
                            color: '#ffffff',
                            connectorColor: '#000000',
                            formatter: function() {
                                return '<b>'+ this.point.name +'</b>: '+ this.percentage.toFixed(2) +' %';
                            }
                        }
                    }
                },
                series: [data.series]
            });
        });
    };

    function pretty_number(num, opts) {
        var defaultOpts = {
            short: true,
            lowerCase: false,
            addCommas: true,
            round: 2
        };

        if (typeof num != "number") {
            return "";
        }

        function round(num, dec) {
            num = num * Math.pow(10, dec);
            num = Math.round(num);
            num /= Math.pow(10, dec);
            return num;
        }

        if (typeof opts == 'undefined') {
            opts = {};
        }

        for (var i in defaultOpts) {
            opts[i] = (typeof opts[i] != 'undefined')? opts[i] : defaultOpts[i];
        }

        if (opts.short) {
            var decimal_places = Math.floor(Math.log(num) / Math.log(10));
            var dec = [{
                'suffix': 'TiB',
                'divisor': 12
            },{
                'suffix': 'GiB',
                'divisor': 9
            },{
                'suffix': 'MiB',
                'divisor': 6
            },{
                'suffix': 'KyB',
                'divisor': 3
            },{
                'suffix': '',
                'divisor': 0
            }];

            for (var i in dec) {
                if (decimal_places > dec[i].divisor) {
                    num = round((num / Math.pow(10, dec[i].divisor)), 2 - (decimal_places - dec[i].divisor));

                    if (num >= 1024 && i > 0) {
                        decimal_places -= 3;
                        num = round(num / 1024, 2 - (decimal_places - dec[i - 1].divisor));
                        num += dec[i - 1].suffix;
                    } else {
                        num += dec[i].suffix;
                    }
                    break;
                }
            }

            num = '' + num;

            if (opts.lowerCase)
            {
                num = num.toLowerCase();
            }
        } else if (opts.addCommas) {
            var decnum = ('' + (round(num, opts.round) - Math.floor(num))).substr(2);
            var tempnum = '' + Math.floor(num);
            num = '';
            for (i = tempnum.length - 1, j = 0; i >= 0; i--, j++) {
                if (j > 0 && j % 3 == 0) {
                    num = ',' + num;
                }
                num = tempnum[i] + num;
            }

            if (decnum > 0) {
                num = num + '.' + decnum;
            }
        }

        return num;
    }

});
