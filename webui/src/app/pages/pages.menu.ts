export const PAGES_MENU = [
  {
    path: ['dashboard'],
    title: 'Dashboard',
    icon: 'ion-android-home',
    selected: false,
    expanded: false,
    order: 0
  },
  {
    title: 'System',
    icon: 'ion-android-options',
    selected: false,
    expanded: false,
    order: 0,
    children: [
      {
        path: ['system', 'general'],
        title: 'General',
        icon: 'ion-earth',
        selected: false,
        expanded: false,
        order: 0
      },
      {
        path: ['system', 'advanced'],
        title: 'Advanced',
        icon: 'ion-ios-cog',
        selected: false,
        expanded: false,
        order: 0
      },
    ]
  },
  {
    title: 'Accounts',
    icon: 'ion-person-stalker',
    selected: false,
    expanded: false,
    order: 0,
    children: [
      {
        path: ['users'],
        title: 'Users',
        icon: 'ion-person',
        selected: false,
        expanded: false,
        order: 0
      },
      {
        path: ['groups'],
        title: 'Groups',
        icon: 'ion-person-stalker',
        selected: false,
        expanded: false,
        order: 0
      },
    ],
  },
  {
    path: ['interfaces'],
    title: 'Interfaces',
    icon: 'ion-network',
    selected: false,
    expanded: false,
    order: 0
  },
  {
    path: ['volumes'],
    title: 'Volumes',
    icon: 'ion-cube',
    selected: false,
    expanded: false,
    order: 0
  },
  {
    title: 'Sharing',
    icon: 'ion-share',
    selected: false,
    expanded: false,
    order: 0,
    children: [
      {
        path: ['sharing', 'afp'],
        title: 'AFP',
        icon: 'ion-social-apple',
        selected: false,
        expanded: false,
        order: 0
      },
      {
        path: ['sharing', 'nfs'],
        title: 'NFS',
        icon: 'ion-social-freebsd-devil',
        selected: false,
        expanded: false,
        order: 0
      },
      {
        path: ['sharing', 'smb'],
        title: 'SMB',
        icon: 'ion-social-windows',
        selected: false,
        expanded: false,
        order: 0
      },
    ],
  },
  {
    path: ['services'],
    title: 'Services',
    icon: 'ion-gear-b',
    selected: false,
    expanded: false,
    order: 0
  },
];
