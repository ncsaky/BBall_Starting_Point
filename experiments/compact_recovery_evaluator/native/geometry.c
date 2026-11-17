/* Narrow recovery geometry batch, binary64, no heap/global retained state.
 * Formula correspondence: nba_gm_data.pass_recovery.recovery_geometry.
 * Numeric comparison ambiguity returns status5 for authoritative Python repair.
 */
#include <math.h>
#include <stddef.h>
#include <stdint.h>
enum {RX,RY,DX,DY,H0,VX,VY,STAND,JUMP,SPAN,ACC,SPEED,DSTAND,DJUMP,DSPAN,DACC,DSPEED,DREACTION,REACTION,HORIZON,VZ,GRAVITY,MINZ,GATHER,TAKEOFF,HALFWIDTH,BACKY,FRONTY,STEPS,BISECTS,AXES,NIN=48};
enum {STATUS,DELAY,CAPTURE,FOOTX,FOOTY,DCX,DCY,BX,BY,BZ,TRAVEL,REACH,DARR,LANDING,SEARCH_HORIZON,OUT_GATHER,NOUT};
static double mn(double a,double b){return b<a?b:a;}
static double mx(double a,double b){return b>a?b:a;}
static double clamp01(double v){return mn(1,mx(0,v));}
static double distance(double ax,double ay,double bx,double by){return hypot(ax-bx,ay-by);}
static double motion(double d,double a,double v){
    if(d<=0)return 0;
    double ramp=v/a,edge=.5*a*ramp*ramp;
    return d<=edge?sqrt(2*d/a):ramp+(d-edge)/v;
}
static int inside(double x,double y,const double *p){return -p[HALFWIDTH]<=x&&x<=p[HALFWIDTH]&&p[BACKY]<=y&&y<=p[FRONTY];}
static int near(double a,double b){return isfinite(a)&&isfinite(b)&&fabs(a-b)<=1e-11*mx(1,mx(fabs(a),fabs(b)));}
static void path(double sx,double sy,double ex,double ey,double elapsed,double delay,double acc,double speed,double *x,double *y){
    double t=mx(0,elapsed-delay),covered=t<=speed/acc?.5*acc*t*t:speed*(t-speed/(2*acc));
    double d=hypot(ex-sx,ey-sy),fraction=clamp01(covered/mx(d,1e-9));
    *x=sx+fraction*(ex-sx);*y=sy+fraction*(ey-sy);
}
/* Candidate -1 ambiguous,0 infeasible,1 feasible. Keep original binary search. */
static int candidate(const double *p,double x0,double y0,double z0,double t,double *values){
    double x=x0+p[VX]*t,y=y0+p[VY]*t,z=z0+p[VZ]*t-.5*p[GRAVITY]*t*t;
    if(near(z,p[MINZ])||near(z,p[STAND]+p[JUMP]))return -1;
    if(z<p[MINZ]||z>p[STAND]+p[JUMP]||!inside(x,y,p))return 0;
    if(near(x,-p[HALFWIDTH])||near(x,p[HALFWIDTH])||near(y,p[BACKY])||near(y,p[FRONTY]))return -1;
    double vertical,reach;
    if(z<=p[STAND]){vertical=0;reach=p[SPAN];}
    else {vertical=mx(0,z-p[STAND])/mx(p[JUMP],1e-9);reach=p[SPAN]*sqrt(mx(0,1-vertical*vertical));}
    double d=distance(p[RX],p[RY],x,y),travel=mx(0,d-reach);
    double required=p[REACTION]+p[TAKEOFF]*vertical+motion(travel,p[ACC],p[SPEED]);
    if(near(required,t)&&!(travel==0&&vertical==0&&!near(d,reach)))return -1;
    if(required>t)return 0;
    double fraction=travel/mx(1e-9,d),fx=p[RX]+fraction*(x-p[RX]),fy=p[RY]+fraction*(y-p[RY]);
    if(!inside(fx,fy,p))return 0;
    values[0]=x;values[1]=y;values[2]=z;values[3]=fx;values[4]=fy;values[5]=travel;values[6]=reach;return 1;
}
int compact_geometry_abi(void){return 1;}
/* Explicit target avoids embedding mutable per-node state in packed inputs. */
int compact_geometry_batch(const double *p,size_t plen,double tx,double ty,const double *errors,const int32_t *dirs,size_t count,double *out,size_t outlen){
    if(!p||!errors||!dirs||!out||plen!=NIN||count>404||outlen<count*NOUT||!isfinite(tx)||!isfinite(ty))return -1;
    for(size_t i=0;i<plen;i++)if(!isfinite(p[i]))return -2;
    if(p[ACC]<=0||p[SPEED]<=0||p[DACC]<=0||p[DSPEED]<=0||p[GRAVITY]<=0||p[HORIZON]<=0||p[JUMP]<0||p[DJUMP]<0||p[SPAN]<=0||p[DSPAN]<=0||p[HALFWIDTH]<=0||p[BACKY]>=p[FRONTY])return -3;
    if(p[STEPS]<1||p[STEPS]>32||p[STEPS]!=floor(p[STEPS])||p[BISECTS]<1||p[BISECTS]>32||p[BISECTS]!=floor(p[BISECTS]))return -4;
    for(size_t i=0;i<count;i++)if(!isfinite(errors[i])||errors[i]<0||dirs[i]<0||dirs[i]>5)return -5;
    for(size_t row=0;row<count;row++){
        double *o=out+row*NOUT;for(int i=0;i<NOUT;i++)o[i]=NAN;
        o[OUT_GATHER]=p[GATHER];double error=errors[row];const double *v=p+AXES+3*dirs[row];
        double x0=tx+error*v[0],y0=ty+error*v[1],z0=p[H0]+error*v[2];
        if(near(x0,-p[HALFWIDTH])||near(x0,p[HALFWIDTH])||near(y0,p[BACKY])||near(y0,p[FRONTY])||near(z0,p[MINZ])){o[STATUS]=5;continue;}
        if(!inside(x0,y0,p)){o[STATUS]=1;o[DELAY]=.05;continue;}
        if(z0<p[MINZ]){o[STATUS]=2;o[DELAY]=.05;continue;}
        double floor_time=(p[VZ]+sqrt(p[VZ]*p[VZ]+2*p[GRAVITY]*(z0-p[MINZ])))/p[GRAVITY];
        double horizon=mn(p[HORIZON],floor_time),exit_time=INFINITY;
        if(p[VX]>0)exit_time=mn(exit_time,(p[HALFWIDTH]-x0)/p[VX]);else if(p[VX]<0)exit_time=mn(exit_time,(-p[HALFWIDTH]-x0)/p[VX]);
        if(p[VY]>0)exit_time=mn(exit_time,(p[FRONTY]-y0)/p[VY]);else if(p[VY]<0)exit_time=mn(exit_time,(p[BACKY]-y0)/p[VY]);
        horizon=mn(horizon,exit_time);o[SEARCH_HORIZON]=horizon;
        int status=0,found=0,ambiguous=0;double cap=NAN,values[7];
        double ex=x0+p[VX]*horizon,ey=y0+p[VY]*horizon;
        double pad=1e-9*mx(1,mx(mx(fabs(p[RX]),fabs(p[RY])),mx(mx(fabs(x0),fabs(y0)),mx(fabs(ex),fabs(ey)))));
        double dx=mx(0,mx(mn(x0,ex)-p[RX],p[RX]-mx(x0,ex))),dy=mx(0,mx(mn(y0,ey)-p[RY],p[RY]-mx(y0,ey)));
        double optimistic=p[REACTION]+motion(mx(0,hypot(dx,dy)-p[SPAN]-3*pad),p[ACC],p[SPEED]);
        int proven=optimistic>horizon+1e-9*mx(1,fabs(horizon))+1e-11;
        if(horizon>=p[REACTION]&&!proven){
            double left=p[REACTION];int steps=(int)p[STEPS],bisects=(int)p[BISECTS];
            for(int step=0;step<=steps;step++){
                double t=p[REACTION]+(horizon-p[REACTION])*step/steps;
                status=candidate(p,x0,y0,z0,t,values);if(status<0){ambiguous=1;break;}
                if(status){
                    double right=t;
                    for(int k=0;k<bisects;k++){
                        double mid=(left+right)/2;status=candidate(p,x0,y0,z0,mid,values);
                        if(status<0){ambiguous=1;break;}if(status==0)left=mid;else right=mid;
                    }
                    if(ambiguous)break;
                    cap=right;status=candidate(p,x0,y0,z0,cap,values);if(status<0){ambiguous=1;break;}
                    if(!status){ambiguous=1;break;}found=1;break;
                }left=t;
            }
        }
        if(ambiguous){o[STATUS]=5;continue;}
        if(!found){
            if(near(exit_time,mn(p[HORIZON],floor_time))||near(floor_time,p[HORIZON])){o[STATUS]=5;continue;}
            o[STATUS]=exit_time<=mn(p[HORIZON],floor_time)?1:floor_time<p[HORIZON]?2:3;o[DELAY]=.05+mx(0,horizon);continue;
        }
        o[CAPTURE]=cap;double bx=values[0],by=values[1],bz=values[2],fx=values[3],fy=values[4];
        double vertical=mx(0,bz-p[DSTAND])/mx(1e-9,p[DJUMP]);
        double dreach=p[DSPAN]*sqrt(mx(0,1-vertical*vertical));
        double darr=bz>p[DSTAND]+p[DJUMP]?NAN:p[DREACTION]+p[TAKEOFF]*vertical+motion(mx(0,distance(p[DX],p[DY],bx,by)-dreach),p[DACC],p[DSPEED]);
        if(near(bz,p[DSTAND]+p[DJUMP])||(isfinite(darr)&&near(darr,cap))){o[STATUS]=5;continue;}
        o[DARR]=darr;
        if(isfinite(darr)&&darr<=cap){o[STATUS]=4;o[DELAY]=.05+darr;continue;}
        double jump=mx(0,bz-p[STAND]),landing=sqrt(2*jump/p[GRAVITY]);
        double delay=mx(.05+error*.25,.05+cap)+landing+p[GATHER];
        double dcx,dcy;path(p[DX],p[DY],fx,fy,delay-.05,p[DREACTION],p[DACC],p[DSPEED],&dcx,&dcy);
        o[STATUS]=0;o[DELAY]=delay;o[FOOTX]=fx;o[FOOTY]=fy;o[DCX]=dcx;o[DCY]=dcy;o[BX]=bx;o[BY]=by;o[BZ]=bz;o[TRAVEL]=values[5];o[REACH]=values[6];o[LANDING]=landing;
    }return 0;
}
