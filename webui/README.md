FreeNAS 11 WebUI
================

This is the project for the new angular.io (4.x) WebUI for FreeNAS 11. It is meant to coexist with current FreeNAS 9.10 Django/Dojo WebUI.

# Development requirements

  - Node.js >= 5, < 7
  - Running FreeNAS 9.10 Nightly (Virtual?) Machine


# Getting started

Install the development requirements (FreeBSD):

```sh
# pkg install node6
# pkg install npm3
```

Checkout FreeNAS git repository:

```sh
$ git clone https://github.com/freenas/freenas.git
$ cd freenas/webui
```

Install npm packages:

```sh
$ npm install
```

Start development server pointing to your FreeNAS machine (in this example, address is 192.168.0.50):

```sh
$ env REMOTE=192.168.0.50
$ npm run server:dev
```

This should open the browser with the WebUI, by default http://localhost:3000.
