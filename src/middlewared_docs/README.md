To test this package, run this in the current directory:

```commandline
mk-build-deps -i
dpkg-buildpackage -us -uc -b && dpkg -i ../middlewared-docs_0.0-1_all.deb  
```

The dpkg-buildpackage step can take several minutes.
