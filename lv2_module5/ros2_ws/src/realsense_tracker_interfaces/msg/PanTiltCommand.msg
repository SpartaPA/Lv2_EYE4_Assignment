# control_node -> opencr_node motor command (team-defined interface, topic /control/pan_tilt_cmd)
# header.stamp : command creation time (control_node clock); opencr_node rejects commands older than 0.15 s
# stop         : true = both axes zero velocity, regardless of the velocity fields
# *_rad_s      : target angular velocity [rad/s] in motor-native sign (direction already applied
#                by control_node), |value| <= 0.05 (firmware MAX_RAD_S)
std_msgs/Header header
bool stop
float32 pan_velocity_rad_s
float32 tilt_velocity_rad_s
