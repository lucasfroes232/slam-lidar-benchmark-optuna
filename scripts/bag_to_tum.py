#!/usr/bin/env python2
import argparse
import rosbag

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bag', required=True)
    p.add_argument('--topic', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--offset', type=float, default=0.0,
                    help='Timestamp de referencia a subtrair (mesmo usado no GT)')
    args = p.parse_args()

    bag = rosbag.Bag(args.bag)
    n = 0
    with open(args.out, 'w') as f:
        for _, msg, _ in bag.read_messages(topics=[args.topic]):
            t = msg.header.stamp.to_sec() - args.offset
            pose = msg.pose.pose if hasattr(msg.pose, 'pose') else msg.pose
            p_, o_ = pose.position, pose.orientation
            f.write('%f %f %f %f %f %f %f %f\n' % (t, p_.x, p_.y, p_.z, o_.x, o_.y, o_.z, o_.w))
            n += 1
    bag.close()
    print('Gerado: %s (%d poses)' % (args.out, n))

if __name__ == '__main__':
    main()