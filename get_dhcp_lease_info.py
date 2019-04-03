#!/usr/bin/python
import datetime, bisect

def parse_timestamp(raw_str):
        #解析时间戳
        tokens = raw_str.split()

        if len(tokens) == 1:
                if tokens[0].lower() == 'never':
                        return 'never';
                else:
                        raise Exception('Parse error in timestamp')

        elif len(tokens) == 3:
                return datetime.datetime.strptime(' '.join(tokens[1:]),
                        '%Y/%m/%d %H:%M:%S')
        else:
                raise Exception('Parse error in timestamp')


def timestamp_is_ge(t1, t2):
        #t1比t2大吗
        if t1 == 'never':
                return True
        elif t2 == 'never':
                return False
        else:
                return t1 >= t2


def timestamp_is_lt(t1, t2):
        # t1比t2小吗
        if t1 == 'never':
                return False
        elif t2 == 'never':
                return t1 != 'never'
        else:
                return t1 < t2


def timestamp_is_between(t, tstart, tend):
        #t在两者之间吗
        return timestamp_is_ge(t, tstart) and timestamp_is_lt(t, tend)


def parse_hardware(raw_str):
        #解析硬件数据
        tokens = raw_str.split()
        if len(tokens) == 2:
                return tokens[1]
        else:
                raise Exception('Parse error in hardware')


def strip_endquotes(raw_str):
        #移除字符串头尾的字符
        return raw_str.strip('"')


def identity(raw_str):
        return raw_str


def parse_binding_state(raw_str):
        #解析binding_state
        tokens = raw_str.split()

        if len(tokens) == 2:
                return tokens[1]
        else:
                raise Exception('Parse error in binding state')


def parse_next_binding_state(raw_str):
        #解析next_binding_state
        tokens = raw_str.split()

        if len(tokens) == 3:
                return tokens[2]
        else:
                raise Exception('Parse error in next binding state')


def parse_rewind_binding_state(raw_str):
        # 解析rewind_binding_state
        tokens = raw_str.split()

        if len(tokens) == 3:
                return tokens[2]
        else:
                raise Exception('Parse error in next binding state')


def parse_leases_file(leases_file):
        valid_keys = {
                'starts':               parse_timestamp,
                'ends':                 parse_timestamp,
                'tstp':                 parse_timestamp,
                'tsfp':                 parse_timestamp,
                'atsfp':                parse_timestamp,
                'cltt':                 parse_timestamp,
                'hardware':             parse_hardware,
                'binding':              parse_binding_state,
                'next':                 parse_next_binding_state,
                'rewind':               parse_rewind_binding_state,
                'uid':                  strip_endquotes,
                'client-hostname':      strip_endquotes,
                'option':               identity,
                'set':                  identity,
                'on':                   identity,
                'abandoned':            None,
                'bootp':                None,
                'reserved':             None,
                }

        leases_db = {}

        lease_rec = {}
        in_lease = False
        in_failover = False

        for line in leases_file:
                #跳过注释
                if line.lstrip().startswith('#'):
                        continue

                tokens = line.split()

                #跳过空行
                if len(tokens) == 0:
                        continue

                key = tokens[0].lower()

                if key == 'lease':
                        if not in_lease:
                                ip_address = tokens[1]
                                lease_rec = {'ip_address' : ip_address}
                                in_lease = True
                        else:
                                raise Exception('Parse error in leases file')

                elif key == 'failover':
                        in_failover = True

                elif key == '}':
                        if in_lease:
                                #填充空键
                                for k in valid_keys:
                                        if callable(valid_keys[k]):
                                                lease_rec[k] = lease_rec.get(k, '')
                                        else:
                                                lease_rec[k] = False
                                ip_address = lease_rec['ip_address']
                                #将lease_rec更新到leases_db
                                if ip_address in leases_db:
                                        leases_db[ip_address].insert(0, lease_rec)
                                else:
                                        leases_db[ip_address] = [lease_rec]
                                #清空lease_rec，准备下一轮
                                lease_rec = {}
                                in_lease = False

                        elif in_failover:
                                in_failover = False
                                continue

                        else:
                                raise Exception('Parse error in leases file')

                elif key in valid_keys:
                        if in_lease:
                                #截取key之后的字符串
                                value = line[(line.index(key) + len(key)):]
                                #移除头尾的空格和分号
                                value = value.strip().rstrip(';').rstrip()
                                #调用对应函数
                                if callable(valid_keys[key]):
                                        lease_rec[key] = valid_keys[key](value)
                                else:
                                        lease_rec[key] = True
                        else:
                                raise Exception('Parse error in leases file')
                else:
                        if in_lease:
                                raise Exception('Parse error in leases file')

        if in_lease:
                raise Exception('Parse error in leases file')

        return leases_db


def round_timedelta(tdelta):
        #获取实践差，两个date或datetime对象相减时可以返回一个timedelta对象
        return datetime.timedelta(tdelta.days,
                tdelta.seconds + (0 if tdelta.microseconds < 500000 else 1))


def timestamp_now():
        #获取当前世界时间
        n = datetime.datetime.utcnow()
        return datetime.datetime(n.year, n.month, n.day, n.hour, n.minute,
                n.second + (0 if n.microsecond < 500000 else 1))


def lease_is_active(lease_rec, as_of_ts):
        #检验处于租期区间的lease，即active lease
        return timestamp_is_between(as_of_ts, lease_rec['starts'],
                lease_rec['ends'])


def ipv4_to_int(ipv4_addr):
        parts = ipv4_addr.split('.')
        #左移操作后输出
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + \
                (int(parts[2]) << 8) + int(parts[3])


def select_active_leases(leases_db, as_of_ts):
        #两个list，将会存储active lease和active ip
        retarray = []
        sortedarray = []

        for ip_address in leases_db:
                lease_rec = leases_db[ip_address][0]

                if lease_is_active(lease_rec, as_of_ts):
                        ip_as_int = ipv4_to_int(ip_address)
                        #获取插入sortedarray并保持有序的位置，返回下标
                        insertpos = bisect.bisect(sortedarray, ip_as_int)
                        #将IP插入
                        sortedarray.insert(insertpos, ip_as_int)
                        #将lease_rec插入retarray
                        retarray.insert(insertpos, lease_rec)

        return retarray


##############################################################################


myfile = open('/var/lib/dhcp/dhcpd.leases', 'r')
leases = parse_leases_file(myfile)
myfile.close()

#report_dataset为lease的list
now = timestamp_now()
report_dataset = select_active_leases(leases, now)

print('+------------------------------------------------------------------------------')
print('| DHCPD ACTIVE LEASES REPORT')
print('+-----------------+-------------------+----------------------+-----------------')
print('| IP Address      | MAC Address       | Expires (days,H:M:S) | Client Hostname ')
print('+-----------------+-------------------+----------------------+-----------------')

for lease in report_dataset:
        print('| ' + format(lease['ip_address'], '<15') + ' | ' + \
                format(lease['hardware'], '<17') + ' | ' + \
                format(str((lease['ends'] - now) if lease['ends'] != 'never' else 'never'), '>20') + ' | ' + \
                lease['client-hostname'])

print('+-----------------+-------------------+----------------------+-----------------')
print('| Total Active Leases: ' + str(len(report_dataset)))
print('| Report generated (UTC): ' + str(now))
print('+------------------------------------------------------------------------------')