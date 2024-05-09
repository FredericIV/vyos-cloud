-- TSIG key for DDNS updates
insert into tsigkeys (name, algorithm, secret) values ('dhcp', 'hmac-md5', '58ctFmMRRsidu8Zz8JkhYuMjr+91ILivMdQsoGwhP9w=');

-- DDNS Domain
insert into domains (name, type) values ('k.fabiv.pw', 'NATIVE');
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = 'k.fabiv.pw'),
  'k.fabiv.pw',
  'SOA',
  'ns.k.fabiv.pw hostmaster.fabiv.pw 0 10 5 600000 5'
);
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = 'k.fabiv.pw'),
  'k.fabiv.pw',
  'NS',
  'ns.k.fabiv.pw'
);
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = 'k.fabiv.pw'),
  'ns.k.fabiv.pw',
  'A',
  '192.168.20.219'
);
insert into domainmetadata (domain_id, kind, content) values
(
    (select id from domains where name = 'k.fabiv.pw'),
    'TSIG-ALLOW-DNSUPDATE',
    'dhcp'
);

-- PTR f/ DDNS
insert into domains (name, type) values ('168.192.in-addr.arpa', 'NATIVE');
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = '168.192.in-addr.arpa'),
  '168.192.in-addr.arpa',
  'SOA',
  'ns.k.fabiv.pw hostmaster.fabiv.pw 0 10 5 600000 5'
);
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = '168.192.in-addr.arpa'),
  '168.192.in-addr.arpa',
  'NS',
  'ns.k.fabiv.pw'
);
insert into records (domain_id, name, type, content) values
(
  (select id from domains where name = '168.192.in-addr.arpa'),
  '219.20.168.192.in-addr.arpa',
  'PTR',
  'ns.k.fabiv.pw'
);
insert into domainmetadata (domain_id, kind, content) values
(
    (select id from domains where name = '168.192.in-addr.arpa'),
    'TSIG-ALLOW-DNSUPDATE',
    'dhcp'
);